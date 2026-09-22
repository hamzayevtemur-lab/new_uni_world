"""
backend/ai/ocr_scanner.py
==========================
AI-Assisted Passport & Travel Document OCR & Information Extraction Pipeline
using Classical Computer Vision, PyTorch Feature Extraction, and HuggingFace TrOCR

Architecture Pipeline:
  Stage 1 — OpenCV Preprocessing (implemented from scratch)
             Grayscale → Gaussian Blur (5x5) → Adaptive Gaussian Thresholding → Hough Deskew
  Stage 2 — Multi-Factor Image Quality Assessment
             Combines interpretable classical CV metrics (Laplacian blur variance,
             mean brightness, RMS contrast) with MobileNetV3 Shannon activation entropy.
             Honest labeling: measures scan clarity, not passport authenticity.
  Stage 3 — MRZ Region Localization (OpenCV morphological operations)
             Detects and crops Machine Readable Zone in the bottom strip of the data page.
  Stage 4 — Dual-Engine OCR Text Extraction
             - Primary:   Pytesseract (fast, structured MRZ reader with PSM 6 & whitelist)
             - Secondary: HuggingFace TrOCR (microsoft/trocr-base-printed)
                          Vision Encoder-Decoder Transformer (ViT + RoBERTa) fallback.
  Stage 5 — ICAO 9303 Check-Digit Validation & NER Parser (implemented from scratch)
             Parses TD3 (Passport) MRZ fields and verifies checksums using the official
             ICAO 9303 7-3-1 modulo 10 weighting algorithm.
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
# 1. Image Quality Assessment (Classical CV + MobileNetV3 Feature Complexity)
# ─────────────────────────────────────────────────────────────────────────────
# Real-world document AI requires multi-factor quality checks:
#   1. Blur / Sharpness:  Variance of Laplacian (Var(∇²I))
#   2. Illumination:      Mean pixel luminance distribution
#   3. Contrast:          Standard deviation of pixel intensities (RMS contrast)
#   4. Semantic Texture:  Shannon activation entropy from MobileNetV3 backbone

def create_quality_scoring_model():
    """
    Loads MobileNetV3-Small with ImageNet pretrained weights.
    Freezes backbone — used strictly as a feature extractor to assess visual complexity.
    """
    model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
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


def compute_image_quality_score(img_cv: np.ndarray, img_rgb: Optional[np.ndarray] = None) -> Dict[str, Any]:
    """
    Computes an interpretable, multi-factor image quality assessment.

    Components:
      - Sharpness (35%): Laplacian variance (var < 80 = blurry, > 250 = sharp)
      - Contrast (25%): Pixel intensity standard deviation (std > 40 = good)
      - Brightness (20%): Mean pixel intensity (optimal: 70 - 190)
      - Complexity (20%): MobileNetV3 feature activation entropy

    Returns structured dictionary with individual metrics and overall score [0, 100].
    """
    if img_cv is None:
        return {
            "image_quality_score": 50.0,
            "quality_label": "UNKNOWN",
            "is_sharp": False,
            "is_well_lit": False,
            "has_good_contrast": False,
            "model_used": "Fallback (no image)"
        }

    # 1. Classical CV Metrics
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY) if len(img_cv.shape) == 3 else img_cv
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean_brightness = float(np.mean(gray))
    contrast_std = float(np.std(gray))

    is_sharp = laplacian_var >= 80.0
    is_well_lit = 50.0 <= mean_brightness <= 210.0
    has_good_contrast = contrast_std >= 30.0

    # Normalized component scores (0.0 to 100.0)
    sharpness_score = min(100.0, max(0.0, (laplacian_var / 250.0) * 100.0))
    contrast_score = min(100.0, max(0.0, (contrast_std / 55.0) * 100.0))
    brightness_score = max(0.0, 100.0 - (abs(mean_brightness - 130.0) / 130.0) * 100.0)

    # 2. Deep Learning Feature Activation Entropy (MobileNetV3)
    entropy = 3.5
    entropy_score = 70.0
    if HAVE_MOBILENET and img_rgb is not None:
        try:
            tensor_img = mobilenet_transform(img_rgb).unsqueeze(0)
            with torch.no_grad():
                feature_maps = mobilenet_model.features(tensor_img)
                pooled = mobilenet_model.avgpool(feature_maps).squeeze()
                activations = pooled.numpy()
                activations_abs = np.abs(activations) + 1e-8
                p = activations_abs / activations_abs.sum()
                entropy = float(-np.sum(p * np.log(p + 1e-10)))
            entropy_score = min(100.0, max(0.0, (entropy - 1.0) / 5.0 * 100.0))
        except Exception:
            pass

    # 3. Weighted Multi-Factor Score
    overall_quality = round(
        0.35 * sharpness_score +
        0.25 * contrast_score +
        0.20 * brightness_score +
        0.20 * entropy_score,
        1
    )

    if overall_quality >= 75:
        label = "EXCELLENT"
    elif overall_quality >= 55:
        label = "GOOD"
    elif overall_quality >= 38:
        label = "ACCEPTABLE"
    else:
        label = "POOR — Retake Scan Recommended"

    return {
        "image_quality_score": overall_quality,
        "quality_label": label,
        "is_sharp": is_sharp,
        "is_well_lit": is_well_lit,
        "has_good_contrast": has_good_contrast,
        "metrics": {
            "laplacian_blur_variance": round(laplacian_var, 1),
            "mean_brightness": round(mean_brightness, 1),
            "contrast_std": round(contrast_std, 1),
            "mobilenet_feature_entropy": round(entropy, 4)
        },
        "model_used": "OpenCV Classical Metrics + MobileNetV3-Small Feature Extractor"
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. TrOCR — Printed Document Text Recognition Model
# ─────────────────────────────────────────────────────────────────────────────
# microsoft/trocr-base-printed is a Vision Encoder–Decoder Transformer:
#   Encoder: ViT (Vision Transformer image patch encoder)
#   Decoder: RoBERTa-based autoregressive text generation decoder

try:
    from transformers import (
        VisionEncoderDecoderModel,
        ViTImageProcessor,
        RobertaTokenizer,
        TrOCRProcessor,
    )

    TROCR_MODEL_NAME = "microsoft/trocr-base-printed"
    vit_image_processor = ViTImageProcessor.from_pretrained(TROCR_MODEL_NAME)
    roberta_tokenizer   = RobertaTokenizer.from_pretrained(TROCR_MODEL_NAME)

    trocr_processor = TrOCRProcessor(
        image_processor=vit_image_processor,
        tokenizer=roberta_tokenizer
    )

    trocr_model = VisionEncoderDecoderModel.from_pretrained(TROCR_MODEL_NAME)
    trocr_model.eval()
    HAVE_TROCR = True
    print(f"✅ [HuggingFace / Transformers] Loaded TrOCR: {TROCR_MODEL_NAME}")
    print(f"   Architecture: Vision Encoder-Decoder (ViT Image Patches + RoBERTa Decoder)")

except Exception as e:
    HAVE_TROCR = False
    trocr_processor = None
    trocr_model = None
    TROCR_MODEL_NAME = "microsoft/trocr-base-printed"
    print(f"⚠️  [TrOCR Load Warning]: {e}")


def trocr_read_image(pil_image: Image.Image) -> str:
    """
    Reads a single line of printed text from a PIL Image using TrOCR.
    """
    if not HAVE_TROCR:
        return ""

    try:
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        pixel_values = trocr_processor(
            images=pil_image,
            return_tensors="pt"
        ).pixel_values

        with torch.no_grad():
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
    Splits MRZ strip into top and bottom lines and runs TrOCR on each independently.
    """
    if not HAVE_TROCR or mrz_strip_pil is None:
        return ""

    w, h = mrz_strip_pil.size
    mid = h // 2

    line1_img = mrz_strip_pil.crop((0, 0, w, mid))
    line2_img = mrz_strip_pil.crop((0, mid, w, h))

    text1 = trocr_read_image(line1_img)
    text2 = trocr_read_image(line2_img)

    return f"{text1}\n{text2}".strip()


# ─────────────────────────────────────────────────────────────────────────────
# 3. OpenCV Preprocessing & MRZ Localization Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def preprocess_document_image(img_cv: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Applies classical OpenCV preprocessing:
      1. Grayscale luminance conversion
      2. Gaussian blur (5x5, σ=0) for high-frequency noise suppression
      3. Adaptive Gaussian thresholding for local illumination invariance
      4. Deskew correction via Hough Line Transform
    """
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    binary = cv2.adaptiveThreshold(
        blurred,
        maxValue=255,
        adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        thresholdType=cv2.THRESH_BINARY,
        blockSize=15,
        C=8
    )

    # Deskew via Hough Line Transform
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
                    if abs(angle) < 30:
                        angles.append(angle)

            if angles:
                median_angle = float(np.median(angles))
                if abs(median_angle) > 0.5:
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
        pass

    return gray, binary


def extract_mrz_region(gray: np.ndarray) -> Optional[Image.Image]:
    """
    Localizes the MRZ strip using OpenCV morphological operations.
    Connects characters with a wide horizontal structuring element (30x2)
    and extracts the candidate region in the bottom 45% of the data page.
    """
    try:
        h, w = gray.shape
        roi_top = int(h * 0.55)
        roi = gray[roi_top:, :]

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 2))
        dilated = cv2.dilate(cv2.bitwise_not(roi), kernel, iterations=3)

        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)

        candidate_rects = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            aspect_ratio = cw / (ch + 1e-5)
            if cw > w * 0.40 and aspect_ratio > 5:
                candidate_rects.append((x, y + roi_top, cw, ch))

        if candidate_rects:
            candidate_rects.sort(key=lambda r: r[1])
            top_y = max(0, candidate_rects[0][1] - 15)
            bot_y = min(h, candidate_rects[-1][1] + candidate_rects[-1][3] + 15)
            mrz_strip = gray[top_y:bot_y, :]
            return Image.fromarray(mrz_strip)

        # Fallback: bottom 30% of image
        return Image.fromarray(gray[int(h * 0.70):, :])

    except Exception:
        return Image.fromarray(gray)


# ─────────────────────────────────────────────────────────────────────────────
# 4. ICAO 9303 Check-Digit Algorithm & TD3 MRZ Parser
# ─────────────────────────────────────────────────────────────────────────────

def calculate_icao_check_digit(data_str: str) -> int:
    """
    Computes ICAO Document 9303 Part 4 check digit.

    Algorithm:
      Weights: [7, 3, 1] repeating pattern modulo 10.
      Character values:
        '0'-'9': 0 - 9
        'A'-'Z': 10 - 35
        '<':     0
    """
    weights = [7, 3, 1]
    total = 0
    for i, ch in enumerate(data_str.upper()):
        if '0' <= ch <= '9':
            val = int(ch)
        elif 'A' <= ch <= 'Z':
            val = ord(ch) - ord('A') + 10
        elif ch == '<':
            val = 0
        else:
            val = 0
        total += val * weights[i % 3]
    return total % 10


def parse_td3_mrz(line1: str, line2: str) -> Dict[str, Any]:
    """
    Parses a TD3 (Passport) MRZ according to ICAO 9303 Part 4 and performs
    checksum verification across document number, birth date, and expiry date.
    """
    l1 = re.sub(r'[^A-Z0-9<]', '<', line1.upper())
    l2 = re.sub(r'[^A-Z0-9<]', '<', line2.upper())

    # Pad to standard 44 characters
    l1 = (l1 + '<' * 44)[:44]
    l2 = (l2 + '<' * 44)[:44]

    # ── Line 1 Extraction ───────────────────────────────────────────────────
    country = l1[2:5].replace('<', '').strip()

    name_section = l1[5:44]
    if '<<' in name_section:
        surname_raw, given_raw = name_section.split('<<', 1)
        surname = surname_raw.replace('<', ' ').strip().title()
        given   = given_raw.replace('<', ' ').strip().title()
        full_name = f"{given} {surname}".strip()
    else:
        full_name = name_section.replace('<', ' ').strip().title()

    # ── Line 2 Extraction & Verification ───────────────────────────────────
    passport_raw = l2[0:9]
    passport_num = passport_raw.replace('<', '').strip()
    passport_check_char = l2[9]

    nationality = l2[10:13].replace('<', '').strip()

    dob_raw = l2[13:19]
    dob_check_char = l2[19]

    sex_char = l2[20] if len(l2) > 20 else '<'
    gender = "Male" if sex_char == 'M' else "Female" if sex_char == 'F' else "Unspecified"

    exp_raw = l2[21:27]
    exp_check_char = l2[27]

    # Date of birth formatting
    if dob_raw.isdigit():
        yy = int(dob_raw[:2])
        # Use dynamic cutoff based on century context
        year = 1900 + yy if yy > 25 else 2000 + yy
        dob = f"{year}-{dob_raw[2:4]}-{dob_raw[4:6]}"
    else:
        dob = "Not Detected"

    # Expiry date formatting
    if exp_raw.isdigit():
        exp_yy = int(exp_raw[:2])
        exp_year = 2000 + exp_yy
        expiry = f"{exp_year}-{exp_raw[2:4]}-{exp_raw[4:6]}"
    else:
        expiry = "Not Detected"

    # ── ICAO 9303 Checksum Validation ───────────────────────────────────────
    passport_valid = (
        passport_check_char.isdigit() and
        calculate_icao_check_digit(passport_raw) == int(passport_check_char)
    )
    dob_valid = (
        dob_check_char.isdigit() and
        calculate_icao_check_digit(dob_raw) == int(dob_check_char)
    )
    exp_valid = (
        exp_check_char.isdigit() and
        calculate_icao_check_digit(exp_raw) == int(exp_check_char)
    )

    # Composite check digit (covers document number + DOB + expiry + optional data)
    composite_data = l2[0:10] + l2[13:20] + l2[21:43]
    composite_check_char = l2[43]
    composite_valid = (
        composite_check_char.isdigit() and
        calculate_icao_check_digit(composite_data) == int(composite_check_char)
    )

    checks = [passport_valid, dob_valid, exp_valid]
    passed_count = sum(1 for c in checks if c)
    total_checks = len(checks)

    return {
        "mrz_extracted": True,
        "mrz_standard": "ICAO 9303 TD3 (Passport)",
        "passport_number": passport_num if passport_num else "Not Detected",
        "full_name": full_name if full_name else "Not Detected",
        "nationality": nationality if nationality else country,
        "date_of_birth": dob,
        "gender": gender,
        "passport_expiry": expiry,
        "mrz_validation": {
            "passport_number_valid": passport_valid,
            "dob_valid": dob_valid,
            "expiry_valid": exp_valid,
            "composite_valid": composite_valid,
            "checks_passed": passed_count,
            "total_checks": total_checks,
            "is_checksum_verified": passed_count == total_checks
        }
    }


def extract_mrz_from_text(ocr_text: str) -> Optional[Dict[str, Any]]:
    """
    Searches OCR output for ICAO 9303 TD3 MRZ line patterns and extracts structured fields.
    """
    if not ocr_text:
        return None

    raw_lines = [l.strip() for l in ocr_text.strip().splitlines() if l.strip()]
    candidate_lines = []

    for line in raw_lines:
        cleaned = re.sub(r'[\s\-]+', '<', line.upper())
        cleaned = re.sub(r'[^A-Z0-9<]', '', cleaned)
        if len(cleaned) >= 35:
            candidate_lines.append(cleaned)

    # Strategy 1: Pairwise line evaluation
    for i in range(len(candidate_lines)):
        l1 = candidate_lines[i]
        if l1.startswith(('P', 'V', 'C', 'I')):
            for j in range(i + 1, len(candidate_lines)):
                l2 = candidate_lines[j]
                if sum(c.isdigit() for c in l2) >= 5:
                    return parse_td3_mrz(l1, l2)

    # Strategy 2: Continuous text regex search
    full_cleaned = re.sub(r'[\s\-]+', '<', ocr_text.upper())
    full_cleaned = re.sub(r'[^A-Z0-9<]', '<', full_cleaned)

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
    End-to-End AI-Assisted Document OCR & Extraction Pipeline.

    Returns structured passport fields, image quality report, checksum verification,
    and a mathematically grounded reliability score.
    """
    result_base = {
        "document_type": "Passport / Travel Document",
        "mrz_extracted": False,
        "mrz_standard": "ICAO 9303 TD3",
    }

    try:
        # Decode image
        nparr = np.frombuffer(image_bytes, np.uint8)
        img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img_cv is None:
            return {
                **result_base,
                "error": "Could not decode image. Please upload JPG or PNG.",
                "passport_number": "Not Detected",
                "full_name": "Not Detected",
                "image_quality": {"quality_label": "UNKNOWN"},
                "extraction_reliability_score": 0.0,
                "confidence_score": 0.0
            }

        # Stage 1: Classical Preprocessing
        img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
        gray, binary = preprocess_document_image(img_cv)

        # Stage 2: Multi-Factor Quality Assessment (Blur + Brightness + Contrast + MobileNet)
        quality_info = compute_image_quality_score(img_cv, img_rgb)

        # Stage 3: MRZ Localization
        mrz_pil = extract_mrz_region(gray)

        # Stage 4: Dual-Engine OCR
        ocr_text = ""
        ocr_source = "none"
        trocr_output = ""
        mrz_fields = None

        # Primary: Pytesseract on cropped MRZ
        try:
            import pytesseract
            if mrz_pil is not None:
                tess_text = pytesseract.image_to_string(
                    mrz_pil,
                    config='--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<'
                )
                mrz_fields = extract_mrz_from_text(tess_text)
                if mrz_fields:
                    ocr_text = tess_text
                    ocr_source = "Pytesseract (primary MRZ reader)"

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

        # Secondary: TrOCR Deep Learning Fallback
        if mrz_fields is None and HAVE_TROCR and mrz_pil is not None:
            trocr_output = read_mrz_lines_with_trocr(mrz_pil)
            if trocr_output:
                mrz_fields = extract_mrz_from_text(trocr_output)
                if mrz_fields:
                    ocr_text = trocr_output
                    ocr_source = "TrOCR (microsoft/trocr-base-printed)"

        # Stage 5: Response Assembly & Reliability Computation
        response = {
            "document_type": "Passport / Travel Document",
            "image_quality": quality_info,
            "ocr_engine": ocr_source if ocr_source != "none" else "Not Available",
            "trocr_model": TROCR_MODEL_NAME if HAVE_TROCR else "Not Loaded",
            "trocr_output": trocr_output if trocr_output else "(skipped: primary OCR succeeded)" if mrz_fields else "(not available)",
            "vision_model": "MobileNetV3-Small (ImageNet pretrained, feature extractor)",
        }

        if mrz_fields:
            response.update(mrz_fields)
            validation = mrz_fields.get("mrz_validation", {})
            check_rate = validation.get("checks_passed", 0) / max(1, validation.get("total_checks", 3))
            quality_norm = quality_info["image_quality_score"] / 100.0
            format_norm = 1.0 if (mrz_fields.get("passport_number") != "Not Detected" and mrz_fields.get("full_name") != "Not Detected") else 0.5

            # Mathematically-grounded Extraction Reliability Score
            reliability = round(0.45 * check_rate + 0.35 * quality_norm + 0.20 * format_norm, 2)
            response["extraction_reliability_score"] = reliability
            response["confidence_score"] = reliability  # Backward compatibility
        else:
            response.update({
                "mrz_extracted": False,
                "passport_number": "Not Detected",
                "full_name": "Not Detected",
                "nationality": "Not Detected",
                "date_of_birth": "Not Detected",
                "gender": "Not Detected",
                "passport_expiry": "Not Detected",
                "extraction_reliability_score": 0.0,
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
            "extraction_reliability_score": 0.0,
            "confidence_score": 0.0,
            "image_quality": {"quality_label": "UNKNOWN"},
            "note": "Pipeline error. Please try again with a clearer image."
        }
