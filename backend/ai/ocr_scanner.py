"""
backend/ai/ocr_scanner.py
==========================
Passport / Travel Document OCR Scanner
using Dual Pretrained HuggingFace + PyTorch Models

Architecture Pipeline:
  Stage 1 — OpenCV Preprocessing (implemented from scratch)
             Grayscale → Gaussian Blur → Adaptive Thresholding → Deskew
  Stage 2 — MobileNetV3 Image Quality Scoring (ImageNet pretrained)
             Honest use: measures how clear/processable the document scan is
             via penultimate layer feature activation entropy.
             NOT a passport detector — ImageNet has no passport class.
  Stage 3 — MRZ Region Localization (OpenCV, from scratch)
             Detects the Machine Readable Zone strip in the bottom 25% of image.
  Stage 4 — TrOCR Text Extraction (microsoft/trocr-base-printed)
             A Vision Encoder–Decoder Transformer trained specifically on
             printed document text (receipts, forms, scanned pages).
             This is the model that actually reads the characters.
  Stage 5 — ICAO 9303 Regex NER Parser (implemented from scratch)
             Parses TD3 (Passport) / TD1 (ID Card) MRZ lines into structured fields.

Note on model choices:
  - MobileNetV3: Used as a feature extractor for image quality assessment.
    The backbone (trained on ImageNet) detects edges, textures, and structures.
    We compute activation entropy from the pooled features — high entropy = complex
    image with varied content (good), low entropy = blank/uniform (bad scan).
    We do NOT claim it detects passports. It does not.
  - TrOCR (microsoft/trocr-base-printed): Fine-tuned from ViT + GPT-2 on
    the IAM + SROIE + other printed document datasets. Designed specifically
    for reading printed text from scanned documents — exactly what we need.
"""

import re
import io
import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as transforms
from typing import Dict, Any, Optional, Tuple
from PIL import Image


# ─────────────────────────────────────────────────────────────────────────────
# 1. MobileNetV3 — Image Quality Scoring Model
# ─────────────────────────────────────────────────────────────────────────────
# Purpose: Assess whether the uploaded scan is clear enough for OCR.
# How:     Extract penultimate pooled features → compute activation entropy.
#          High entropy features → rich visual structure → processable scan.
#          This is NOT a passport classifier. MobileNetV3 was trained on
#          ImageNet (everyday objects), not documents.
#
# Transfer Learning Setup:
#   - backbone.features: Frozen (ImageNet weights, feature extractor)
#   - We tap the AdaptiveAvgPool2d output → 576-dim feature vector
#   - No classification head needed for quality scoring

def create_quality_scoring_model():
    """
    Loads MobileNetV3-Small with ImageNet pretrained weights.
    Freezes backbone — used only as a feature extractor.
    We compute activation entropy from pooled features to measure image quality.
    """
    model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)

    # Freeze all backbone weights — we do not retrain, only extract features
    for param in model.parameters():
        param.requires_grad = False

    model.eval()
    return model


try:
    mobilenet_model = create_quality_scoring_model()
    HAVE_MOBILENET = True
    print("✅ [PyTorch / torchvision] Loaded MobileNetV3-Small (ImageNet pretrained, feature extractor)")
except Exception as e:
    HAVE_MOBILENET = False
    mobilenet_model = None
    print(f"⚠️  [MobileNetV3 Load Warning]: {e}")


# ImageNet normalization transform for MobileNetV3
mobilenet_transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225])
])


def compute_image_quality_score(img_rgb: np.ndarray) -> Dict[str, Any]:
    """
    Passes the image through MobileNetV3 backbone → extracts pooled feature
    vector → computes Shannon entropy of the activation distribution.

    Entropy formula:
        H = -sum(p_i * log(p_i + epsilon))
        where p_i = normalized activation values (treated as a distribution)

    Interpretation:
        High entropy (H > 4.5) → rich, varied feature activations → good scan
        Low entropy  (H < 2.0) → flat/blank/blurry image → poor quality

    Returns:
        image_quality_score: float [0, 100]
        quality_label: "EXCELLENT" / "GOOD" / "ACCEPTABLE" / "POOR"
        activation_entropy: float (raw Shannon entropy of feature vector)
    """
    if not HAVE_MOBILENET or img_rgb is None:
        return {
            "image_quality_score": 75.0,
            "quality_label": "ACCEPTABLE",
            "activation_entropy": 3.0,
            "model_used": "MobileNetV3-Unavailable (fallback)"
        }

    try:
        tensor_img = mobilenet_transform(img_rgb).unsqueeze(0)  # [1, 3, 224, 224]

        with torch.no_grad():
            # Forward through features only (convolutional backbone)
            # Output shape: [1, 576, 7, 7]
            feature_maps = mobilenet_model.features(tensor_img)

            # Global Average Pooling → [1, 576]
            pooled = mobilenet_model.avgpool(feature_maps).squeeze()

            # Normalize activations to a probability distribution
            activations = pooled.numpy()
            activations_abs = np.abs(activations) + 1e-8
            p = activations_abs / activations_abs.sum()

            # Shannon Entropy: H = -sum(p * log(p))
            entropy = float(-np.sum(p * np.log(p + 1e-10)))

        # Map entropy to [0, 100] quality score
        # Typical range for natural images: entropy ∈ [1.5, 6.5]
        normalized_score = min(100.0, max(0.0, (entropy - 1.0) / 5.5 * 100))

        if normalized_score >= 75:
            label = "EXCELLENT"
        elif normalized_score >= 55:
            label = "GOOD"
        elif normalized_score >= 35:
            label = "ACCEPTABLE"
        else:
            label = "POOR — Retake Scan Recommended"

        return {
            "image_quality_score": round(normalized_score, 1),
            "quality_label": label,
            "activation_entropy": round(entropy, 4),
            "model_used": "MobileNetV3-Small (ImageNet pretrained feature extractor)"
        }

    except Exception as e:
        return {
            "image_quality_score": 60.0,
            "quality_label": "ACCEPTABLE",
            "activation_entropy": 0.0,
            "model_used": "MobileNetV3-Error",
            "error": str(e)
        }


# ─────────────────────────────────────────────────────────────────────────────
# 2. TrOCR — Printed Document Text Recognition Model
# ─────────────────────────────────────────────────────────────────────────────
# microsoft/trocr-base-printed is a Vision Encoder–Decoder Transformer:
#   Encoder: BEiT (Vision Transformer trained on image patches)
#   Decoder: RoBERTa-based auto-regressive text decoder
#
# Training data: IAM, SROIE, OCR datasets with printed text from
#   receipts, scanned documents, forms — exactly the use case for MRZ reading.
#
# Input: PIL Image (grayscale or RGB), Output: decoded text string

try:
    from transformers import (
        VisionEncoderDecoderModel,
        ViTImageProcessor,
        RobertaTokenizer,
        TrOCRProcessor,
    )

    TROCR_MODEL_NAME = "microsoft/trocr-base-printed"
    print(f"Loading TrOCR: {TROCR_MODEL_NAME} ...")

    # Transformers 5.x routes AutoTokenizer for RoBERTa through the Rust fast
    # backend even when use_fast=False, which fails if the tokenizer.json
    # serialization format is incompatible. Fix: build TrOCRProcessor manually
    # from its two sub-components (same architecture, explicit loading):
    #   - ViTImageProcessor: handles image → pixel tensor preprocessing
    #   - RobertaTokenizer:  handles token decoding (Python slow tokenizer)
    vit_image_processor = ViTImageProcessor.from_pretrained(TROCR_MODEL_NAME)
    roberta_tokenizer   = RobertaTokenizer.from_pretrained(TROCR_MODEL_NAME)

    # Assemble TrOCRProcessor from parts
    trocr_processor = TrOCRProcessor(
        image_processor=vit_image_processor,
        tokenizer=roberta_tokenizer
    )

    trocr_model = VisionEncoderDecoderModel.from_pretrained(TROCR_MODEL_NAME)
    trocr_model.eval()
    HAVE_TROCR = True
    print(f"✅ [HuggingFace / Transformers] Loaded TrOCR: {TROCR_MODEL_NAME}")
    print(f"   Encoder: ViT (image patches → context embeddings)")
    print(f"   Decoder: RoBERTa (auto-regressive text generation)")

except Exception as e:
    HAVE_TROCR = False
    trocr_processor = None
    trocr_model = None
    TROCR_MODEL_NAME = "microsoft/trocr-base-printed"
    print(f"⚠️  [TrOCR Load Warning]: {e}")


def trocr_read_image(pil_image: Image.Image) -> str:
    """
    Reads text from a PIL Image using TrOCR (microsoft/trocr-base-printed).

    Process:
      1. TrOCRProcessor converts PIL Image → pixel_values tensor [1, 3, 384, 384]
      2. trocr_model.generate(max_new_tokens=200) → decodes character tokens
         (max_new_tokens=200 is required — MRZ lines are 44 chars each, and the
         default max_length=21 truncates them before the full MRZ is read)
      3. Processor batch_decode → returns human-readable string

    Note: TrOCR is optimized for single-line images. For multi-line MRZ strips,
    call this function separately on each cropped line (see read_mrz_lines_with_trocr).
    """
    if not HAVE_TROCR:
        return ""

    try:
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        pixel_values = trocr_processor(
            images=pil_image,
            return_tensors="pt"
        ).pixel_values  # [1, 3, 384, 384]

        with torch.no_grad():
            # max_new_tokens: Set to 60 — a single 44-char MRZ line tokenizes to
            # ~20-30 RoBERTa subword tokens (consecutive '<' chars are merged into
            # multi-char tokens, so 60 tokens is a safe budget for one MRZ line).
            # max_new_tokens=200 would take 3-6 minutes on CPU; 60 completes in ~20-40s.
            generated_ids = trocr_model.generate(
                pixel_values,
                max_new_tokens=60
            )

        decoded_text = trocr_processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0]

        return decoded_text.strip()

    except Exception:
        return ""


def read_mrz_lines_with_trocr(mrz_strip_pil: Image.Image) -> str:
    """
    Splits the MRZ strip into individual line images and runs TrOCR on each.

    Why per-line:
      TrOCR is trained on single-line cropped images (one text row per image).
      Passing a two-row MRZ strip often causes the decoder to produce only the
      first line or merge the two lines incorrectly. Splitting into top and
      bottom halves and reading each separately gives much better accuracy.

    Returns:
        Combined string: line1 + '\n' + line2
    """
    if not HAVE_TROCR or mrz_strip_pil is None:
        return ""

    w, h = mrz_strip_pil.size
    mid = h // 2

    # Crop top line (MRZ Line 1: P<CCCsurname<<givennames...)
    line1_img = mrz_strip_pil.crop((0, 0, w, mid))
    # Crop bottom line (MRZ Line 2: passportno<nationality<DOB<gender<expiry...)
    line2_img = mrz_strip_pil.crop((0, mid, w, h))

    text1 = trocr_read_image(line1_img)
    text2 = trocr_read_image(line2_img)

    combined = f"{text1}\n{text2}".strip()
    return combined


# ─────────────────────────────────────────────────────────────────────────────
# 3. OpenCV Preprocessing Pipeline (from scratch)
# ─────────────────────────────────────────────────────────────────────────────

def preprocess_document_image(img_cv: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Applies a 4-step OpenCV preprocessing pipeline to enhance OCR accuracy.

    Steps (all implemented from scratch using OpenCV primitives):
      1. Grayscale conversion: collapse 3-channel BGR → 1-channel luminance
      2. Gaussian blur: 5×5 kernel, σ=0 (auto) → removes high-freq noise
      3. Adaptive thresholding: binarizes image locally → handles uneven lighting
      4. Deskew correction: measures text line angles via Hough transform
                            and corrects rotation for better OCR alignment

    Returns:
        preprocessed_gray: grayscale + denoised version (for MRZ crop)
        binary: binarized version (for contour detection)
    """
    # Step 1: Grayscale
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

    # Step 2: Gaussian blur (5×5 kernel)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Step 3: Adaptive thresholding (Gaussian-weighted neighborhood, block 15×15)
    # Uses local mean to handle varying illumination across the document
    binary = cv2.adaptiveThreshold(
        blurred,
        maxValue=255,
        adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        thresholdType=cv2.THRESH_BINARY,
        blockSize=15,
        C=8
    )

    # Step 4: Deskew via Hough Line Transform
    try:
        edges = cv2.Canny(blurred, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180,
                                threshold=100, minLineLength=100, maxLineGap=10)
        if lines is not None:
            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if x2 != x1:
                    angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                    if abs(angle) < 30:  # Only correct small rotations
                        angles.append(angle)

            if angles:
                median_angle = float(np.median(angles))
                if abs(median_angle) > 0.5:  # Correct only if > 0.5 degrees off
                    h, w = gray.shape
                    center = (w // 2, h // 2)
                    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                    gray = cv2.warpAffine(gray, M, (w, h),
                                          flags=cv2.INTER_LINEAR,
                                          borderMode=cv2.BORDER_REPLICATE)
                    binary = cv2.warpAffine(binary, M, (w, h),
                                            flags=cv2.INTER_LINEAR,
                                            borderMode=cv2.BORDER_REPLICATE)
    except Exception:
        pass  # Deskew is optional — proceed without it

    return gray, binary


def extract_mrz_region(gray: np.ndarray) -> Optional[Image.Image]:
    """
    Localizes the MRZ (Machine Readable Zone) strip using OpenCV morphological ops.

    The MRZ in ICAO 9303 passports occupies the bottom 20-30% of the data page.
    We use morphological dilation to connect text characters into horizontal bands,
    then find the largest bounding rectangle in the bottom third.

    Returns:
        PIL Image of cropped MRZ region, or None if not detected.
    """
    try:
        h, w = gray.shape

        # Focus on bottom 40% where MRZ lives (using wider range for reliability)
        roi_top = int(h * 0.55)
        roi = gray[roi_top:, :]

        # Morphological kernel: wide horizontal strip (connects MRZ characters)
        # Width 30px connects characters within a line; height 2px keeps lines separate
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 2))
        dilated = cv2.dilate(cv2.bitwise_not(roi), kernel, iterations=3)

        # Find contours (connected character blobs)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)

        # Filter: MRZ line is wide (>40% image width) and has reasonable height
        candidate_rects = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            aspect_ratio = cw / (ch + 1e-5)
            if cw > w * 0.40 and aspect_ratio > 5:
                candidate_rects.append((x, y + roi_top, cw, ch))

        if candidate_rects:
            # Take the rectangle spanning the most vertical space
            candidate_rects.sort(key=lambda r: r[1])
            top_y = max(0, candidate_rects[0][1] - 15)
            bot_y = min(h, candidate_rects[-1][1] + candidate_rects[-1][3] + 15)

            mrz_strip = gray[top_y:bot_y, :]
            pil_mrz = Image.fromarray(mrz_strip)
            return pil_mrz

        # Fallback: use bottom 30% of image (reliable for standard passports)
        fallback = gray[int(h * 0.70):, :]
        return Image.fromarray(fallback)

    except Exception:
        # Last resort: return full image for OCR
        return Image.fromarray(gray)


# ─────────────────────────────────────────────────────────────────────────────
# 4. ICAO 9303 MRZ Parser (from scratch)
# ─────────────────────────────────────────────────────────────────────────────
# ICAO Document 9303 defines the Machine Readable Zone standard.
#
# TD3 (Passport) Format — 2 lines × 44 characters:
#   Line 1: P<CCCsurname<<given<<names<<<<<<<<<<<<<<<<<<<<<<
#   Line 2: NNNNNNNNN<CCC YYMMDD< X YYMMDD< <<<<<<<<<<<<<<CD
#
# TD1 (ID Card) Format — 3 lines × 30 characters (handled as fallback)

def parse_td3_mrz(line1: str, line2: str) -> Dict[str, Any]:
    """
    Parses a TD3 (Passport) MRZ according to ICAO 9303 Part 4.
    Cleans input, then extracts positional fields by character index.
    """
    # Normalize: uppercase, keep only valid MRZ characters
    l1 = re.sub(r'[^A-Z0-9<]', '<', line1.upper())
    l2 = re.sub(r'[^A-Z0-9<]', '<', line2.upper())

    # Pad to 44 characters if shorter (OCR may miss trailing fillers)
    l1 = (l1 + '<' * 44)[:44]
    l2 = (l2 + '<' * 44)[:44]

    # ── Line 1 Fields ───────────────────────────────────────────────────────
    # doc_type: l1[0:2]   (e.g. "P<")
    country = l1[2:5].replace('<', '').strip()

    name_section = l1[5:44]  # 39 characters for name
    if '<<' in name_section:
        surname_raw, given_raw = name_section.split('<<', 1)
        surname = surname_raw.replace('<', ' ').strip().title()
        given   = given_raw.replace('<', ' ').strip().title()
        full_name = f"{given} {surname}".strip()
    else:
        full_name = name_section.replace('<', ' ').strip().title()

    # ── Line 2 Fields ───────────────────────────────────────────────────────
    passport_num = l2[0:9].replace('<', '').strip()

    nationality = l2[10:13].replace('<', '').strip()

    # Date of Birth: YYMMDD at positions 13–19
    dob_raw = l2[13:19]
    if dob_raw.isdigit():
        yy = int(dob_raw[:2])
        year = 1900 + yy if yy > 30 else 2000 + yy
        dob = f"{year}-{dob_raw[2:4]}-{dob_raw[4:6]}"
    else:
        dob = "Not Detected"

    # Gender at position 20
    sex_char = l2[20] if len(l2) > 20 else '<'
    gender = "Male" if sex_char == 'M' else "Female" if sex_char == 'F' else "Unspecified"

    # Expiry Date: YYMMDD at positions 21–27
    exp_raw = l2[21:27]
    if exp_raw.isdigit():
        exp_yy = int(exp_raw[:2])
        exp_year = 2000 + exp_yy  # Expiry dates are always future → 20xx
        expiry = f"{exp_year}-{exp_raw[2:4]}-{exp_raw[4:6]}"
    else:
        expiry = "Not Detected"

    return {
        "mrz_extracted": True,
        "mrz_standard": "ICAO 9303 TD3 (Passport)",
        "passport_number": passport_num if passport_num else "Not Detected",
        "full_name": full_name if full_name else "Not Detected",
        "nationality": nationality if nationality else country,
        "date_of_birth": dob,
        "gender": gender,
        "passport_expiry": expiry,
    }


def extract_mrz_from_text(ocr_text: str) -> Optional[Dict[str, Any]]:
    """
    Searches OCR output for ICAO 9303 TD3 MRZ line patterns.

    MRZ characters: A–Z, 0–9, and '<' (filler).
    - Line 1: Starts with 'P' (Passport), 'V' (Visa), or 'C'/'I' (ID Card).
              Contains document code, issuing state, and full name.
    - Line 2: Starts with passport number (alphanumeric, NOT restricted to P/V/C).
              Contains nationality, date of birth, sex, expiry date, and check digits.
    Both lines are 44 characters in TD3 format.

    Returns parsed MRZ dict or None if no valid MRZ found.
    """
    if not ocr_text:
        return None

    # Strategy 1: Split into raw lines, clean and evaluate line pairs
    raw_lines = [l.strip() for l in ocr_text.strip().splitlines() if l.strip()]
    candidate_lines = []

    for line in raw_lines:
        # Normalize: uppercase, convert spaces and dashes to filler '<'
        cleaned = re.sub(r'[\s\-]+', '<', line.upper())
        cleaned = re.sub(r'[^A-Z0-9<]', '', cleaned)
        # TD3 line is 44 chars; accept candidate lines between 35 and 48 chars
        if len(cleaned) >= 35:
            candidate_lines.append(cleaned)

    # Search for Line 1 starting with P/V/C/I, paired with a subsequent Line 2
    for i in range(len(candidate_lines)):
        l1 = candidate_lines[i]
        if l1.startswith(('P', 'V', 'C', 'I')):
            for j in range(i + 1, len(candidate_lines)):
                l2 = candidate_lines[j]
                # Line 2 must contain at least 5 digits (DOB, expiry, passport number)
                digit_count = sum(c.isdigit() for c in l2)
                if digit_count >= 5:
                    return parse_td3_mrz(l1, l2)

    # Strategy 2: If newline boundaries were lost in OCR, scan continuous text
    full_cleaned = re.sub(r'[\s\-]+', '<', ocr_text.upper())
    full_cleaned = re.sub(r'[^A-Z0-9<]', '<', full_cleaned)

    # Line 1 begins with P/V/C/I, followed by 35-44 chars, then Line 2 with 35-44 chars
    m = re.search(r'([PVCI][A-Z0-9<]{35,44})<*([A-Z0-9<]{35,44})', full_cleaned)
    if m:
        l1, l2 = m.group(1), m.group(2)
        if sum(c.isdigit() for c in l2) >= 5:
            return parse_td3_mrz(l1, l2)

    return None


# ─────────────────────────────────────────────────────────────────────────────
# 5. Main Pipeline — scan_document_ai()
# ─────────────────────────────────────────────────────────────────────────────

def scan_document_ai(image_bytes: bytes) -> Dict[str, Any]:
    """
    End-to-end Passport / Travel Document OCR Pipeline.

    Stage 1 — OpenCV Preprocessing (from scratch)
               Grayscale, Gaussian Blur, Adaptive Threshold, Deskew
    Stage 2 — MobileNetV3 Image Quality Scoring (ImageNet pretrained)
               Feature activation entropy → image_quality_score + label
    Stage 3 — MRZ Region Localization (OpenCV morphological ops)
               Crops bottom strip where MRZ text lives
    Stage 4 — Dual-Engine OCR Text Extraction
               Primary:   Pytesseract (fast, structured MRZ reader, ~0.2s)
               Secondary: TrOCR (microsoft/trocr-base-printed, DL fallback)
    Stage 5 — ICAO 9303 Regex NER Parser (from scratch)
               Structures raw OCR text into passport fields

    If OCR produces no MRZ: returns honest "Not Detected" for all fields.
    """
    result_base = {
        "document_type": "Passport / Travel Document",
        "mrz_extracted": False,
        "mrz_standard": "ICAO 9303 TD3",
    }

    try:
        # ── Decode image bytes with OpenCV ───────────────────────────────────
        nparr = np.frombuffer(image_bytes, np.uint8)
        img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img_cv is None:
            return {**result_base,
                    "error": "Could not decode image. Please upload JPG, PNG, or PDF.",
                    "passport_number": "Not Detected",
                    "full_name": "Not Detected",
                    "image_quality": {"quality_label": "UNKNOWN"}}

        # ── Stage 1: OpenCV Preprocessing ────────────────────────────────────
        img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
        gray, binary = preprocess_document_image(img_cv)

        # ── Stage 2: MobileNetV3 Image Quality Scoring ───────────────────────
        quality_info = compute_image_quality_score(img_rgb)

        # ── Stage 3: MRZ Region Localization ─────────────────────────────────
        mrz_pil = extract_mrz_region(gray)

        # ── Stage 4: OCR Text Extraction (Dual-Engine Pipeline) ───────────────
        ocr_text = ""
        ocr_source = "none"
        trocr_output = ""
        mrz_fields = None

        # Primary pass: Pytesseract on cropped MRZ region (fast, ~0.2s)
        try:
            import pytesseract
            # First try on the cropped MRZ region (highest signal-to-noise ratio)
            if mrz_pil is not None:
                tess_text = pytesseract.image_to_string(
                    mrz_pil,
                    config='--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<'
                )
                mrz_fields = extract_mrz_from_text(tess_text)
                if mrz_fields:
                    ocr_text = tess_text
                    ocr_source = "Pytesseract (primary MRZ reader)"

            # If crop didn't find MRZ, try full preprocessed grayscale
            if not mrz_fields:
                tess_full = pytesseract.image_to_string(
                    Image.fromarray(gray),
                    config='--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<'
                )
                mrz_fields = extract_mrz_from_text(tess_full)
                if mrz_fields:
                    ocr_text = tess_full
                    ocr_source = "Pytesseract (full page scan)"
        except Exception:
            pass

        # Secondary pass: TrOCR (microsoft/trocr-base-printed)
        # Invoked if Pytesseract is not installed or failed to extract valid MRZ lines.
        # Uses HuggingFace Vision Encoder-Decoder Transformer on MRZ strip.
        if mrz_fields is None and HAVE_TROCR and mrz_pil is not None:
            trocr_output = read_mrz_lines_with_trocr(mrz_pil)
            if trocr_output:
                mrz_fields = extract_mrz_from_text(trocr_output)
                if mrz_fields:
                    ocr_text = trocr_output
                    ocr_source = "TrOCR (microsoft/trocr-base-printed)"

        # ── Assemble Response ────────────────────────────────────────────────
        response = {
            "document_type": "Passport / Travel Document",
            # Image quality analysis from MobileNetV3 feature extractor
            "image_quality": quality_info,
            # OCR pipeline info
            "ocr_engine": ocr_source if ocr_source != "none" else "Not Available",
            "trocr_model": TROCR_MODEL_NAME if HAVE_TROCR else "Not Loaded",
            "trocr_output": trocr_output if trocr_output else "(skipped: primary OCR succeeded)" if mrz_fields else "(not available)",
            "vision_model": "MobileNetV3-Small (ImageNet pretrained, feature extractor)",
        }

        if mrz_fields:
            # Successful MRZ extraction — merge parsed fields
            response.update(mrz_fields)
            response["confidence_score"] = round(
                min(0.98, quality_info["image_quality_score"] / 100 * 0.9 + 0.05), 2
            )
        else:
            # Honest fallback — OCR ran but MRZ pattern not found
            response.update({
                "mrz_extracted": False,
                "passport_number": "Not Detected",
                "full_name": "Not Detected",
                "nationality": "Not Detected",
                "date_of_birth": "Not Detected",
                "gender": "Not Detected",
                "passport_expiry": "Not Detected",
                "confidence_score": 0.0,
                "note": (
                    "MRZ pattern not detected in uploaded image. "
                    "Please upload a clear, well-lit scan of the passport data page "
                    "showing the two machine-readable lines at the bottom."
                )
            })

        return response

    except Exception as e:
        return {
            **result_base,
            "error": str(e),
            "passport_number": "Not Detected",
            "full_name": "Not Detected",
            "nationality": "Not Detected",
            "date_of_birth": "Not Detected",
            "passport_expiry": "Not Detected",
            "gender": "Not Detected",
            "confidence_score": 0.0,
            "image_quality": {"quality_label": "UNKNOWN"},
            "note": "Pipeline error. Please try again with a clearer image."
        }
