import psycopg2
import psycopg2.extras
from config import DATABASE_URL

def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

def init_db():
    """Initializes all standard and CRM tables automatically on startup."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Comments table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id          SERIAL PRIMARY KEY,
                name        VARCHAR(100),
                country     VARCHAR(100),
                rating      INT,
                comment_text TEXT,
                is_approved BOOLEAN DEFAULT FALSE,
                created_at  TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # News table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id          SERIAL PRIMARY KEY,
                title       VARCHAR(255) NOT NULL,
                body        TEXT NOT NULL,
                badge_text  VARCHAR(80),
                image_url   VARCHAR(500),
                link_url    VARCHAR(500),
                link_text   VARCHAR(100),
                expires_at  TIMESTAMP,
                is_active   BOOLEAN DEFAULT TRUE,
                is_ticker   BOOLEAN DEFAULT FALSE,
                created_at  TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # Countries table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS countries (
                id                SERIAL PRIMARY KEY,
                name              VARCHAR(100) NOT NULL,
                flag_emoji        VARCHAR(10),
                university_count  VARCHAR(50),
                description       TEXT,
                image_url         VARCHAR(500),
                modal_key         VARCHAR(50),
                programs          TEXT,
                cost_of_living    VARCHAR(100),
                language          TEXT,
                visa_requirements TEXT,
                sort_order        INT DEFAULT 0,
                is_active         BOOLEAN DEFAULT TRUE,
                created_at        TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # Services table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id            SERIAL PRIMARY KEY,
                title         VARCHAR(200) NOT NULL,
                icon_emoji    VARCHAR(10),
                image_url     VARCHAR(500),
                description   TEXT,
                details       TEXT,
                benefits      TEXT,
                is_featured   BOOLEAN DEFAULT FALSE,
                modal_key     VARCHAR(50),
                sort_order    INT DEFAULT 0,
                is_active     BOOLEAN DEFAULT TRUE,
                created_at    TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # Universities table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS universities (
                id           SERIAL PRIMARY KEY,
                name         VARCHAR(200) NOT NULL,
                country      VARCHAR(100),
                image_url    VARCHAR(500),
                description  TEXT,
                programs     TEXT,
                ranking      VARCHAR(100),
                link_url     VARCHAR(500),
                sort_order   INT DEFAULT 0,
                is_active    BOOLEAN DEFAULT TRUE,
                created_at   TIMESTAMP DEFAULT NOW()
            );
        """)

        # Leads table (captured inquiries)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id              SERIAL PRIMARY KEY,
                name            VARCHAR(150) NOT NULL,
                phone           VARCHAR(50) NOT NULL,
                email           VARCHAR(255),
                country         VARCHAR(100),
                message         TEXT,
                status          VARCHAR(30) DEFAULT 'new',
                created_at      TIMESTAMP DEFAULT NOW()
            );
        """)

        # Students CRM table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id                  SERIAL PRIMARY KEY,
                email               VARCHAR(255) UNIQUE NOT NULL,
                password_hash       VARCHAR(255),
                full_name           VARCHAR(200) NOT NULL,
                phone               VARCHAR(50),
                date_of_birth       VARCHAR(30),
                gender              VARCHAR(20),
                nationality         VARCHAR(100) DEFAULT 'Uzbekistan',
                passport_number     VARCHAR(50),
                passport_expiry     VARCHAR(30),
                address             TEXT,
                emergency_contact   VARCHAR(150),
                high_school_name    VARCHAR(255),
                gpa                 VARCHAR(50),
                ielts_score         VARCHAR(50),
                duolingo_score      VARCHAR(50),
                target_country      VARCHAR(100),
                target_degree       VARCHAR(50),
                target_major        VARCHAR(150),
                status              VARCHAR(50) DEFAULT 'pending',
                email_verified      BOOLEAN DEFAULT FALSE,
                otp_code            VARCHAR(10),
                otp_expires_at      TIMESTAMP,
                approved_at         TIMESTAMP,
                notes               TEXT,
                created_at          TIMESTAMP DEFAULT NOW(),
                updated_at          TIMESTAMP DEFAULT NOW()
            );
        """)

        # Add OTP and verification columns to existing students table if they don't exist yet
        for col, typedef in [
            ("email_verified", "BOOLEAN DEFAULT FALSE"),
            ("otp_code", "VARCHAR(10)"),
            ("otp_expires_at", "TIMESTAMP"),
            ("approved_at", "TIMESTAMP"),
        ]:
            cur.execute(f"""
                DO $$ BEGIN
                    ALTER TABLE students ADD COLUMN {col} {typedef};
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
            """)

        # Allow NULL password_hash for pending access requests
        cur.execute("ALTER TABLE students ALTER COLUMN password_hash DROP NOT NULL;")

        # Student Documents table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS student_documents (
                id              SERIAL PRIMARY KEY,
                student_id      INT REFERENCES students(id) ON DELETE CASCADE,
                doc_type        VARCHAR(50) NOT NULL,
                title           VARCHAR(200) NOT NULL,
                file_url        VARCHAR(1000) NOT NULL,
                file_name       VARCHAR(255),
                file_size       VARCHAR(50),
                status          VARCHAR(30) DEFAULT 'pending',
                admin_feedback  TEXT,
                uploaded_at     TIMESTAMP DEFAULT NOW()
            );
        """)

        # Student University Applications table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS student_applications (
                id                  SERIAL PRIMARY KEY,
                student_id          INT REFERENCES students(id) ON DELETE CASCADE,
                university_name     VARCHAR(255) NOT NULL,
                country             VARCHAR(100),
                program_name        VARCHAR(255),
                intake_semester     VARCHAR(100),
                status              VARCHAR(50) DEFAULT 'Draft',
                portal_url          VARCHAR(1000),
                application_id      VARCHAR(100),
                notes               TEXT,
                created_at          TIMESTAMP DEFAULT NOW(),
                updated_at          TIMESTAMP DEFAULT NOW()
            );
        """)

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[init_db] Note/Warning: {e}")
