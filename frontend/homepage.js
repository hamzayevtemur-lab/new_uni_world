// Country and service data loaded from DB on demand
const _countryCache = {};
const _serviceCache = {};

async function openCountryModal(modalKey) {
    const modal = document.getElementById('countryModal');
    const content = document.getElementById('countryModalContent');
    content.innerHTML = '<div style="text-align:center;padding:2rem;color:#64748b;">Loading...</div>';
    modal.classList.add('active');

    try {
        // Load from cache or fetch
        if (!_countryCache._all) {
            const items = await fetch('/api/countries').then(r => r.json());
            items.forEach(c => { _countryCache[c.modal_key || c.name.toLowerCase()] = c; });
            _countryCache._all = true;
        }
        const data = _countryCache[modalKey] || _countryCache[modalKey.toLowerCase()];
        if (!data) { content.innerHTML = '<p style="text-align:center;padding:2rem;">Country not found.</p>'; return; }

        // Universities from DB for this country
        const unis = await fetch('/api/universities').then(r => r.json());
        const countryUnis = unis.filter(u => u.country && u.country.toLowerCase() === data.name.toLowerCase() && u.is_active);

        const uniList = countryUnis.length
            ? countryUnis.map(u => `<li>${escH(u.name)}${u.ranking ? ' <span style="color:#f59e0b;font-size:0.8em">⭐ '+escH(u.ranking)+'</span>' : ''}</li>`).join('')
            : '<li>Contact us for partner universities</li>';

        const programList = data.programs
            ? data.programs.split(',').map(p => `<li>${escH(p.trim())}</li>`).join('')
            : '';

        content.innerHTML = `
            <div class="modal-header">
                <div class="modal-flag">${escH(data.flag_emoji || '🌍')}</div>
                <h2>${escH(data.name)}</h2>
                <p>${escH(data.university_count || '')}</p>
            </div>
            <div class="modal-body">
                ${data.description ? `<p>${escH(data.description)}</p>` : ''}
                ${countryUnis.length ? `<h3>Partner Universities</h3><ul>${uniList}</ul>` : ''}
                ${programList ? `<h3>Popular Programs</h3><ul>${programList}</ul>` : ''}
                ${data.cost_of_living ? `<h3>Living Costs</h3><p>${escH(data.cost_of_living)}</p>` : ''}
                ${data.language ? `<h3>Language</h3><p>${escH(data.language)}</p>` : ''}
                ${data.visa_requirements ? `<h3>Visa Requirements</h3><p>${escH(data.visa_requirements)}</p>` : ''}
                <div class="modal-cta">
                    <p>Ready to study in ${escH(data.name)}?</p>
                    <a href="#contact">Contact Us Today</a>
                </div>
            </div>`;
    } catch(e) {
        content.innerHTML = '<p style="text-align:center;padding:2rem;color:#ef4444;">Failed to load. Please try again.</p>';
    }
}

async function openServiceModal(modalKey) {
    const modal = document.getElementById('serviceModal');
    const content = document.getElementById('serviceModalContent');
    content.innerHTML = '<div style="text-align:center;padding:2rem;color:#64748b;">Loading...</div>';
    modal.classList.add('active');

    try {
        if (!_serviceCache._all) {
            const items = await fetch('/api/services').then(r => r.json());
            items.forEach(s => { _serviceCache[s.modal_key || s.title.toLowerCase().replace(/\s+/g,'-')] = s; });
            _serviceCache._all = true;
        }
        const data = _serviceCache[modalKey] || _serviceCache[modalKey.toLowerCase()];
        if (!data) { content.innerHTML = '<p style="text-align:center;padding:2rem;">Service not found.</p>'; return; }

        const detailList = data.details
            ? data.details.split('\n').filter(l => l.trim()).map(l => `<li>${escH(l.trim())}</li>`).join('')
            : '';

        content.innerHTML = `
            <div class="modal-header">
                <div class="modal-flag">${escH(data.icon_emoji || '⭐')}</div>
                <h2>${escH(data.title)}</h2>
            </div>
            <div class="modal-body">
                ${data.description ? `<p>${escH(data.description)}</p>` : ''}
                ${detailList ? `<h3>What We Offer</h3><ul>${detailList}</ul>` : ''}
                ${data.benefits ? `<h3>Why Choose This Service?</h3><p>${escH(data.benefits)}</p>` : ''}
                <div class="modal-cta">
                    <p>Want to learn more about this service?</p>
                    <a href="#contact">Schedule a Consultation</a>
                </div>
            </div>`;
    } catch(e) {
        content.innerHTML = '<p style="text-align:center;padding:2rem;color:#ef4444;">Failed to load. Please try again.</p>';
    }
}


function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// Close modal when clicking outside
window.onclick = function (event) {
    if (event.target.classList.contains('modal')) {
        event.target.classList.remove('active');
    }
}

function handleSubmit(e) {
    e.preventDefault();

    const form = e.target;
    const submitBtn = document.getElementById('submitBtn');
    const formStatus = document.getElementById('formStatus');
    const formData = new FormData(form);

    // Disable button and show loading
    submitBtn.disabled = true;
    submitBtn.textContent = 'Sending...';
    formStatus.innerHTML = '<span style="color: #3d6fa6;">⏳ Sending your message...</span>';

    // Get form values
    const data = {
        name: formData.get('name'),
        email: formData.get('email'),
        phone: formData.get('phone'),
        country: formData.get('country'),
        message: formData.get('message')
    };

    // OPTION 1: Using Formspree (Recommended)
    // Replace 'YOUR_FORM_ID' with your actual Formspree form ID
    // Get it from: https://formspree.io (free account)

    fetch('https://formspree.io/f/mykgrkbl', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
        .then(response => {
            if (response.ok) {
                formStatus.innerHTML = '<span style="color: #10b981;">✅ Message sent successfully! We will contact you soon.</span>';
                form.reset();
            } else {
                throw new Error('Failed to send');
            }
        })
        .catch(error => {
            // Fallback to mailto if Formspree fails or not configured
            formStatus.innerHTML = '<span style="color: #ef4444;">⚠️ Using backup method...</span>';

            const subject = `Inquiry from ${data.name} - Study in ${data.country}`;
            const body = `Name: ${data.name}%0D%0AEmail: ${data.email}%0D%0APhone: ${data.phone}%0D%0APreferred Country: ${data.country}%0D%0A%0D%0AMessage:%0D%0A${data.message}`;
            const mailtoLink = `mailto:info@uniworld.uz?subject=${subject}&body=${body}`;

            window.location.href = mailtoLink;

            setTimeout(() => {
                formStatus.innerHTML = '<span style="color: #3d6fa6;">📧 Please send the email from your email client.</span>';
            }, 1000);
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Send Message';
        });
}

// Smooth scrolling for navigation links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Language Switcher
let currentLang = 'en';

function switchLanguage(lang) {
    currentLang = lang;

    // Update active button
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');

    // Update all translatable elements
    document.querySelectorAll('[data-en]').forEach(element => {
        if (lang === 'en') {
            if (element.tagName === 'H2' && element.innerHTML.includes('<span>')) {
                // Handle hero title with span
                element.innerHTML = element.getAttribute('data-en');
            } else {
                element.textContent = element.getAttribute('data-en');
            }
        } else {
            if (element.tagName === 'H2' && element.innerHTML.includes('<span>')) {
                // Handle hero title with span
                element.innerHTML = element.getAttribute('data-uz');
            } else {
                element.textContent = element.getAttribute('data-uz');
            }
        }
    });

    // Update stats
    updateStats(lang);

    // Update section headers
    updateSectionHeaders(lang);
}

function updateStats(lang) {
    const stats = {
        en: {
            students: 'Students Placed',
            universities: 'Partner Universities',
            countries: 'Countries Covered',
            success: 'Success Rate'
        },
        uz: {
            students: 'Joylashtirilgan Talabalar',
            universities: 'Hamkor Universitetlar',
            countries: 'Qamrab Olingan Mamlakatlar',
            success: 'Muvaffaqiyat Darajasi'
        }
    };

    document.querySelectorAll('.stat-label').forEach((label, index) => {
        const keys = Object.keys(stats[lang]);
        if (keys[index]) {
            label.textContent = stats[lang][keys[index]];
        }
    });
}

function updateSectionHeaders(lang) {
    const headers = {
        en: {
            aboutBadge: 'About Us',
            aboutTitle: 'Partner With Our <span>Trusted Consultants</span> Today',
            aboutText1: 'At Uni World, we are a trusted educational consulting firm dedicated to helping students achieve their dreams of studying abroad. Our team of experienced consultants brings diverse industry knowledge and expertise in international admissions.',
            aboutText2: 'We understand your unique challenges and goals to deliver customized solutions tailored to your specific needs. We are committed to providing exceptional service, innovative strategies, and tangible results for our students.',
            aboutBtn: 'Learn More About Us',

            countriesBadge: 'Study Destinations',
            countriesTitle: 'Countries We Serve',
            countriesDesc: 'Explore world-class education opportunities across 8 countries with our expert guidance',

            servicesBadge: 'Our Services',
            servicesTitle: 'Consulting Services We Offer',
            servicesDesc: 'Our team of experienced consultants combines industry knowledge, cutting-edge strategies, and innovative approaches to guide you towards a brighter future.',

            processTitle: 'Our Simple 4-Step Process',
            processDesc: 'From initial consultation to university enrollment, we guide you every step of the way',

            contactBadge: 'Get In Touch',
            contactTitle: 'Ready to Start Your Journey?',
            contactDesc: 'Contact us today for a free consultation and take the first step towards your dream education'
        },
        uz: {
            aboutBadge: 'Biz Haqimizda',
            aboutTitle: 'Bugun <span>Ishonchli Maslahatchilarimiz</span> Bilan Hamkorlik Qiling',
            aboutText1: 'Uni World - bu talabalarning chet elda o\'qish orzularini amalga oshirishga yordam beradigan ishonchli ta\'lim konsalting firmasi. Bizning tajribali maslahatchilar jamoamiz xalqaro qabul bo\'yicha turli sohalar bilimi va tajribasiga ega.',
            aboutText2: 'Biz sizning noyob muammolaringiz va maqsadlaringizni tushunamiz va sizning ehtiyojlaringizga moslashtirilgan yechimlarni taqdim etamiz. Biz talabalarga ajoyib xizmat, innovatsion strategiyalar va aniq natijalarni taqdim etishga sodiqmiz.',
            aboutBtn: 'Biz Haqimizda Batafsil',

            countriesBadge: 'O\'qish Yo\'nalishlari',
            countriesTitle: 'Biz Xizmat Ko\'rsatadigan Mamlakatlar',
            countriesDesc: 'Bizning professional yo\'l-yo\'rig\'imiz bilan 8 mamlakatda jahon darajasidagi ta\'lim imkoniyatlarini o\'rganing',

            servicesBadge: 'Bizning Xizmatlar',
            servicesTitle: 'Biz Taklif Qiladigan Konsalting Xizmatlari',
            servicesDesc: 'Tajribali maslahatchilar jamoamiz sanoat bilimi, zamonaviy strategiyalar va innovatsion yondashuvlarni birlashtirib, sizni yorqin kelajakka yo\'naltiradi.',

            processTitle: 'Bizning Oddiy 4 Bosqichli Jarayon',
            processDesc: 'Dastlabki konsultatsiyadan universitetga ro\'yxatdan o\'tishgacha har bir bosqichda sizga yo\'l-yo\'riq ko\'rsatamiz',

            contactBadge: 'Bog\'lanish',
            contactTitle: 'Sayohatingizni Boshlashga Tayyormisiz?',
            contactDesc: 'Bugun bepul konsultatsiya uchun biz bilan bog\'laning va orzuingizdagi ta\'limga birinchi qadamni qo\'ying'
        }
    };

    const h = headers[lang];

    // About section
    document.querySelector('.about-badge').textContent = h.aboutBadge;
    document.querySelector('.about-content h2').innerHTML = h.aboutTitle;
    const aboutPs = document.querySelectorAll('.about-content p');
    if (aboutPs[0]) aboutPs[0].textContent = h.aboutText1;
    if (aboutPs[1]) aboutPs[1].textContent = h.aboutText2;
    document.querySelector('.about-btn').textContent = h.aboutBtn;

    // Countries section
    document.querySelector('.countries-badge').textContent = h.countriesBadge;
    document.querySelector('.countries-header h2').textContent = h.countriesTitle;
    document.querySelector('.countries-header p').textContent = h.countriesDesc;

    // Services section
    document.querySelector('.services-badge').textContent = h.servicesBadge;
    document.querySelector('.services-header h2').textContent = h.servicesTitle;
    document.querySelector('.services-header p').textContent = h.servicesDesc;

    // Process section
    document.querySelector('.process-header h2').textContent = h.processTitle;
    document.querySelector('.process-header p').textContent = h.processDesc;

    // Contact section
    document.querySelector('.contact-badge').textContent = h.contactBadge;
    document.querySelector('.contact-header h2').textContent = h.contactTitle;
    document.querySelector('.contact-header p').textContent = h.contactDesc;

    // Update country cards
    updateCountryCards(lang);

    // Update service cards
    updateServiceCards(lang);

    // Update process steps
    updateProcessSteps(lang);

    // Update contact info
    updateContactInfo(lang);
}

function updateCountryCards(lang) {
    const cards = {
        en: ['Partner Universities', 'Partner Universities', 'Partner Universities', 'Partner Universities', 'Partner Universities', 'Partner Universities', 'Partner Universities', 'Partner Universities'],
        uz: ['Hamkor Universitetlar', 'Hamkor Universitetlar', 'Hamkor Universitetlar', 'Hamkor Universitetlar', 'Hamkor Universitetlar', 'Hamkor Universitetlar', 'Hamkor Universitetlar', 'Hamkor Universitetlar']
    };

    const btnText = lang === 'en' ? 'Learn More' : 'Batafsil';

    document.querySelectorAll('.country-card p').forEach((p, index) => {
        const num = p.textContent.match(/\d+\+/)[0];
        p.textContent = `${num} ${cards[lang][index]}`;
    });

    document.querySelectorAll('.country-btn').forEach(btn => {
        btn.textContent = btnText;
    });
}

function updateServiceCards(lang) {
    const services = {
        en: {
            titles: ['Application Assistance', 'University Selection', 'Visa Support', 'Scholarship Guidance', 'Document Preparation', 'Pre-Departure Support'],
            descriptions: [
                'Our experienced consultants help develop strategic plans to prepare competitive university applications, improve your profile, and achieve your admission goals.',
                'Our experts offer market research, program matching, and university selection strategies to enhance your academic journey and ensure the best fit for your goals.',
                'We provide visa application guidance, document preparation, and interview coaching to optimize your visa approval and ensure smooth immigration processes.',
                'We help identify scholarship opportunities, prepare compelling applications, and maximize your funding to make international education more affordable.',
                'Expert assistance with personal statements, recommendation letters, CVs, and all required documents to create a compelling application package.',
                'Comprehensive guidance on accommodation, travel arrangements, cultural preparation, and everything you need for a smooth transition to your new country.'
            ]
        },
        uz: {
            titles: ['Ariza Yordami', 'Universitet Tanlash', 'Viza Yordami', 'Stipendiya Yo\'l-Yo\'rig\'i', 'Hujjat Tayyorlash', 'Jo\'nash Oldidan Yordam'],
            descriptions: [
                'Tajribali maslahatchilarimiz raqobatbardosh universitet arizalarini tayyorlash, profilingizni yaxshilash va qabul maqsadlaringizga erishish uchun strategik rejalar ishlab chiqishda yordam beradi.',
                'Mutaxassislarimiz bozor tadqiqotlari, dastur moslashtirish va universitet tanlash strategiyalarini taklif qiladi, bu akademik sayohatingizni yaxshilaydi va maqsadlaringizga eng mos keladi.',
                'Biz viza arizasi bo\'yicha maslahat, hujjatlarni tayyorlash va intervyu tayyorlashni taqdim etamiz, bu vizangizni tasdiqlashni optimallashtiradi va immigratsiya jarayonlarini soddalashtiradi.',
                'Biz stipendiya imkoniyatlarini aniqlashda, ta\'sirli arizalarni tayyorlashda va xalqaro ta\'limni yanada arzonroq qilish uchun moliyalashtirishni maksimal darajada oshirishda yordam beramiz.',
                'Shaxsiy bayonotlar, tavsiya xatlari, rezyume va barcha kerakli hujjatlar bilan professional yordam, ta\'sirli ariza paketini yaratish.',
                'Turar joy, sayohat tartibotlari, madaniy tayyorgarlik va yangi mamlakatga silliq o\'tish uchun kerak bo\'lgan hamma narsa bo\'yicha keng qamrovli yo\'l-yo\'riq.'
            ]
        }
    };

    const readMore = lang === 'en' ? 'Read More →' : 'Batafsil →';

    document.querySelectorAll('.service-card h3').forEach((h3, index) => {
        h3.textContent = services[lang].titles[index];
    });

    document.querySelectorAll('.service-card p').forEach((p, index) => {
        p.textContent = services[lang].descriptions[index];
    });

    document.querySelectorAll('.service-link').forEach(link => {
        link.textContent = readMore;
    });
}

function updateProcessSteps(lang) {
    const steps = {
        en: {
            titles: ['Initial Consultation', 'University Selection', 'Application Support', 'Visa & Departure'],
            descriptions: [
                'We assess your profile, goals, and preferences to create a personalized roadmap',
                'We identify the best-fit universities and programs based on your aspirations',
                'We help prepare compelling applications and all required documentation',
                'We assist with visa processing and pre-departure preparations'
            ]
        },
        uz: {
            titles: ['Dastlabki Konsultatsiya', 'Universitet Tanlash', 'Ariza Yordami', 'Viza va Jo\'nash'],
            descriptions: [
                'Shaxsiy yo\'l xaritasini yaratish uchun profilingiz, maqsadlaringiz va afzalliklaringizni baholaymiz',
                'Sizning intilishlaringizga asoslangan eng mos universitetlar va dasturlarni aniqlaymiz',
                'Ta\'sirli arizalar va barcha kerakli hujjatlarni tayyorlashda yordam beramiz',
                'Viza jarayoni va jo\'nash oldidan tayyorgarlikda yordam beramiz'
            ]
        }
    };

    document.querySelectorAll('.process-step h3').forEach((h3, index) => {
        h3.textContent = steps[lang].titles[index];
    });

    document.querySelectorAll('.process-step p').forEach((p, index) => {
        p.textContent = steps[lang].descriptions[index];
    });
}

function updateContactInfo(lang) {
    const contact = {
        en: {
            infoTitle: 'Contact Information',
            infoDesc: 'Have questions? We\'re here to help you every step of the way. Reach out through any of these channels.',
            phone: 'Phone',
            email: 'Email',
            office: 'Office',
            officeAddr1: 'Tashkent, Uzbekistan',
            officeAddr2: 'Amir Temur Street 123',
            hours: 'Working Hours',
            hours1: 'Mon - Fri: 9:00 AM - 6:00 PM',
            hours2: 'Sat: 10:00 AM - 4:00 PM',
            formName: 'Full Name *',
            formNamePh: 'Your Name',
            formEmail: 'Email *',
            formEmailPh: 'your@email.com',
            formPhone: 'Phone Number *',
            formCountry: 'Preferred Country *',
            formCountryPh: 'Select a country',
            formMessage: 'Your Message *',
            formMessagePh: 'Tell us about your educational goals and how we can help you...',
            formBtn: 'Send Message'
        },
        uz: {
            infoTitle: 'Aloqa Ma\'lumotlari',
            infoDesc: 'Savollaringiz bormi? Biz har bir bosqichda sizga yordam berishga tayyormiz. Ushbu kanallardan biri orqali bog\'laning.',
            phone: 'Telefon',
            email: 'Elektron pochta',
            office: 'Ofis',
            officeAddr1: 'Toshkent, O\'zbekiston',
            officeAddr2: 'Amir Temur ko\'chasi 123',
            hours: 'Ish Vaqti',
            hours1: 'Dush - Jum: 9:00 - 18:00',
            hours2: 'Shan: 10:00 - 16:00',
            formName: 'To\'liq Ism *',
            formNamePh: 'Ismingiz',
            formEmail: 'Elektron pochta *',
            formEmailPh: 'sizning@email.com',
            formPhone: 'Telefon Raqam *',
            formCountry: 'Afzal Ko\'rilgan Mamlakat *',
            formCountryPh: 'Mamlakatni tanlang',
            formMessage: 'Sizning Xabaringiz *',
            formMessagePh: 'Ta\'lim maqsadlaringiz va biz sizga qanday yordam bera olishimiz haqida bizga xabar bering...',
            formBtn: 'Xabar Yuborish'
        }
    };

    const c = contact[lang];

    document.querySelector('.contact-info h3').textContent = c.infoTitle;
    document.querySelector('.contact-info > p').textContent = c.infoDesc;

    const contactLabels = document.querySelectorAll('.contact-details h4');
    contactLabels[0].textContent = c.phone;
    contactLabels[1].textContent = c.email;
    contactLabels[2].textContent = c.office;
    contactLabels[3].textContent = c.hours;

    const officePs = document.querySelectorAll('.contact-details')[2].querySelectorAll('p');
    officePs[0].textContent = c.officeAddr1;
    officePs[1].textContent = c.officeAddr2;

    const hoursPs = document.querySelectorAll('.contact-details')[3].querySelectorAll('p');
    hoursPs[0].textContent = c.hours1;
    hoursPs[1].textContent = c.hours2;

    // Form labels
    document.querySelectorAll('.form-group label')[0].textContent = c.formName;
    document.querySelectorAll('.form-group label')[1].textContent = c.formEmail;
    document.querySelectorAll('.form-group label')[2].textContent = c.formPhone;
    document.querySelectorAll('.form-group label')[3].textContent = c.formCountry;
    document.querySelectorAll('.form-group label')[4].textContent = c.formMessage;

    // Form placeholders
    document.getElementById('name').placeholder = c.formNamePh;
    document.getElementById('email').placeholder = c.formEmailPh;
    document.getElementById('message').placeholder = c.formMessagePh;

    // Form button
    document.getElementById('submitBtn').textContent = c.formBtn;
}


// API Configuration
const API_URL = '';

let allCommentsShown = false;


// Add new comment
async function addComment(e) {
    e.preventDefault();

    const name = document.getElementById('commentName').value;
    const country = document.getElementById('commentCountry').value;
    const rating = document.querySelector('input[name="rating"]:checked').value;
    const comment_text = document.getElementById('commentText').value;

    const submitBtn = document.querySelector('.submit-comment-btn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting...';

    try {
        const response = await fetch(`${API_URL}/api/comments`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                name,
                country,
                rating: parseInt(rating),
                comment_text
            })
        });

        if (response.ok) {
            alert('Thank you! Your comment will appear after approval.');
            document.getElementById('commentForm').reset();

            // Optionally reload comments (won't show new one until approved)
            // loadComments();
        } else {
            throw new Error('Failed to submit comment');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error submitting comment. Please try again.');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Post Comment';
    }
}



// Global variables
let allComments = [];
let showingAll = false;

// Load comments
async function loadComments() {
    try {
        const response = await fetch(`${API_URL}/api/comments`);
        allComments = await response.json();

        displayComments();

    } catch (error) {
        console.error('Error loading comments:', error);
    }
}

// Display comments based on current state
function displayComments() {
    const commentsList = document.getElementById('commentsList');
    const showMoreContainer = document.getElementById('showMoreContainer');
    const showMoreBtn = document.getElementById('showMoreBtn');

    // Clear existing comments
    commentsList.innerHTML = '';

    // Determine how many to show
    const commentsToShow = showingAll ? allComments : allComments.slice(0, 3);

    // Render comments
    commentsToShow.forEach(comment => {
        const initials = comment.name.split(' ').map(word => word[0]).join('').toUpperCase().substring(0, 2);
        const stars = '⭐'.repeat(comment.rating);
        const date = new Date(comment.created_at);
        const timeAgo = getTimeAgo(date);

        const commentHTML = `
            <div class="comment-card">
                <div class="comment-author">
                    <div class="author-avatar">${initials}</div>
                    <div class="author-details">
                        <h4>${comment.name}</h4>
                        <p class="comment-date">${timeAgo}</p>
                        <p class="comment-country">${comment.country}</p>
                    </div>
                </div>
                <div class="comment-text">
                    "${comment.comment_text}"
                </div>
                <div class="comment-rating">${stars}</div>
            </div>
        `;
        commentsList.innerHTML += commentHTML;
    });

    // Show/hide button
    if (allComments.length > 3) {
        showMoreContainer.style.display = 'block';

        if (showingAll) {
            showMoreBtn.innerHTML = '⬆️ Show Less Comments';
        } else {
            const remaining = allComments.length - 3;
            showMoreBtn.innerHTML = `⬇️ Show More Comments (${remaining} more)`;
        }
    } else {
        showMoreContainer.style.display = 'none';
    }
}

// Toggle function
function toggleComments() {
    showingAll = !showingAll;
    displayComments();

    // Scroll behavior
    if (showingAll) {
        // When showing all, scroll to show more button
        setTimeout(() => {
            document.getElementById('showMoreBtn').scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });
        }, 100);
    } else {
        // When collapsing, scroll to comments section
        setTimeout(() => {
            document.getElementById('commentsList').scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }, 100);
    }
}

// Helper function for time ago (keep this as is)
function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);

    const intervals = {
        year: 31536000,
        month: 2592000,
        week: 604800,
        day: 86400,
        hour: 3600,
        minute: 60
    };

    for (const [unit, secondsInUnit] of Object.entries(intervals)) {
        const interval = Math.floor(seconds / secondsInUnit);
        if (interval >= 1) {
            return `${interval} ${unit}${interval > 1 ? 's' : ''} ago`;
        }
    }

    return 'Just now';
}

// Load comments when page loads
document.addEventListener('DOMContentLoaded', () => {
    loadComments();
    loadNewsAndTicker();
    loadCountries();
    loadServices();
    loadUniversities();
});

// ── Countries ─────────────────────────────────────────────────────────────────

async function loadCountries() {
    try {
        const items = await fetch('/api/countries').then(r => r.json());
        const grid = document.getElementById('countriesGrid');
        if (!grid) return;
        if (!items || !items.length) {
            grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:2rem;color:#94a3b8;">No countries added yet.</div>';
            return;
        }
        grid.innerHTML = items.map(c => `
            <div class="country-card">
                <div class="country-flag">${escH(c.flag_emoji || '🌍')}</div>
                <h3>${escH(c.name)}</h3>
                <p>${escH(c.university_count || '')}</p>
                <button class="country-btn" onclick="openCountryModal('${escH(c.modal_key || c.name.toLowerCase())}')">Learn More</button>
            </div>`).join('');
    } catch(e) { console.log('Countries load error', e); }
}

// ── Services ──────────────────────────────────────────────────────────────────

async function loadServices() {
    try {
        const items = await fetch('/api/services').then(r => r.json());
        const grid = document.getElementById('servicesGrid');
        if (!grid) return;
        if (!items || !items.length) {
            grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:2rem;color:#94a3b8;">No services added yet.</div>';
            return;
        }
        grid.innerHTML = items.map(s => `
            <div class="service-card ${s.is_featured ? 'featured' : ''}">
                <div class="service-icon">${escH(s.icon_emoji || '⭐')}</div>
                <h3>${escH(s.title)}</h3>
                <p>${escH(s.description || '')}</p>
                <button class="service-link" onclick="openServiceModal('${escH(s.modal_key || '')}')">Read More →</button>
            </div>`).join('');
    } catch(e) { console.log('Services load error', e); }
}

// ── Universities ──────────────────────────────────────────────────────────────

async function loadUniversities() {
    try {
        const items = await fetch('/api/universities').then(r => r.json());
        const section = document.getElementById('universities');
        const grid = document.getElementById('universitiesGrid');
        if (!section || !grid || !items || !items.length) return;
        grid.innerHTML = items.map(u => {
            const img = u.image_url
                ? `<img class="uni-card-img" src="${escH(u.image_url)}" alt="${escH(u.name)}" onerror="this.style.display='none'">`
                : `<div class="uni-card-img-placeholder">🎓</div>`;
            const ranking = u.ranking ? `<div class="uni-card-ranking">⭐ ${escH(u.ranking)}</div>` : '';
            const link = u.link_url ? `<a class="uni-card-link" href="${escH(u.link_url)}" target="_blank">Visit Website →</a>` : '';
            return `
                <div class="uni-card">
                    ${img}
                    <div class="uni-card-body">
                        <div class="uni-card-country">${escH(u.country || '')}</div>
                        <div class="uni-card-name">${escH(u.name)}</div>
                        ${ranking}
                        <div class="uni-card-desc">${escH(u.description || '')}</div>
                        ${link}
                    </div>
                </div>`;
        }).join('');
        section.style.display = 'block';
    } catch(e) { console.log('Universities load error', e); }
}

// ── News & Ticker ──────────────────────────────────────────────────────────

const NEWS_API = '';

async function loadNewsAndTicker() {
    try {
        const [newsItems, tickerItems] = await Promise.all([
            fetch(`${NEWS_API}/api/news`).then(r => r.json()),
            fetch(`${NEWS_API}/api/news/ticker`).then(r => r.json()),
        ]);

        if (tickerItems && tickerItems.length > 0) {
            renderTicker(tickerItems);
        }
        if (newsItems && newsItems.length > 0) {
            renderNewsSection(newsItems);
        }
    } catch (e) {
        // News is optional — fail silently
        console.log('News could not be loaded', e);
    }
}

function renderTicker(items) {
    const ticker = document.getElementById('newsTicker');
    const track = document.getElementById('tickerTrack');
    if (!ticker || !track) return;

    // Duplicate items so the scroll loops seamlessly
    const allItems = [...items, ...items];
    track.innerHTML = allItems.map(item => {
        const href = item.link_url ? `onclick="window.open('${escH(item.link_url)}','_blank')"` : '';
        return `<span class="ticker-item" ${href}><span class="ticker-dot">●</span>${escH(item.title)}</span>`;
    }).join('');

    ticker.style.display = 'flex';
}

function renderNewsSection(items) {
    const section = document.getElementById('news');
    const grid = document.getElementById('newsGrid');
    if (!section || !grid) return;

    grid.innerHTML = items.map(newsCardHtml).join('');
    section.style.display = 'block';
}

function newsCardHtml(n) {
    const imgEl = n.image_url
        ? `<img class="nc-img" src="${escH(n.image_url)}" alt="${escH(n.title)}" onerror="this.style.display='none'">`
        : `<div class="nc-img-placeholder">🎓</div>`;
    const badge = n.badge_text ? `<span class="nc-badge">${escH(n.badge_text)}</span>` : '';
    const expires = n.expires_at
        ? `<span class="nc-expires">⏰ Until ${new Date(n.expires_at).toLocaleDateString()}</span>`
        : '';
    const date = new Date(n.created_at).toLocaleDateString('en-US', { day:'numeric', month:'short', year:'numeric' });
    const linkEl = n.link_url
        ? `<a class="nc-link" href="${escH(n.link_url)}" target="_blank">${escH(n.link_text || 'Learn More →')}</a>`
        : '';

    return `
        <div class="news-card-pub">
            ${imgEl}
            <div class="nc-body">
                ${badge}
                <div class="nc-title">${escH(n.title)}</div>
                <div class="nc-body-text">${escH(n.body)}</div>
                <div class="nc-footer">
                    <div>
                        <div class="nc-date">📅 ${date}</div>
                        ${expires}
                    </div>
                    ${linkEl}
                </div>
            </div>
        </div>`;
}

function escH(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g,'&amp;')
        .replace(/</g,'&lt;')
        .replace(/>/g,'&gt;')
        .replace(/"/g,'&quot;')
        .replace(/'/g,'&#39;');
}