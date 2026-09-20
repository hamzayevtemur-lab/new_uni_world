from database import get_conn


def add_column_if_not_exists(cur, table_name, column_name, column_def):
    """Safely adds a column to a MySQL table if it does not already exist."""
    cur.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
    """,
        (table_name, column_name),
    )
    res = cur.fetchone()
    if not res or res.get("cnt", 0) == 0:
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def};")


def init_db():
    """Initializes all MySQL tables and auto-migrations on app startup."""
    try:
        conn = get_conn()
        cur = conn.cursor()

        # Comments table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS comments (
                id           INT AUTO_INCREMENT PRIMARY KEY,
                name         VARCHAR(100),
                country      VARCHAR(100),
                rating       INT,
                comment_text TEXT,
                is_approved  BOOLEAN DEFAULT FALSE,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        )

        # News / Announcements table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS news (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                title       VARCHAR(255) NOT NULL,
                body        TEXT NOT NULL,
                badge_text  VARCHAR(80),
                image_url   VARCHAR(500),
                link_url    VARCHAR(500),
                link_text   VARCHAR(100),
                expires_at  TIMESTAMP NULL DEFAULT NULL,
                is_active   BOOLEAN DEFAULT TRUE,
                is_ticker   BOOLEAN DEFAULT FALSE,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        )

        # Countries table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS countries (
                id                INT AUTO_INCREMENT PRIMARY KEY,
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
                created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        )

        # Services table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS services (
                id            INT AUTO_INCREMENT PRIMARY KEY,
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
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        )

        # Universities table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS universities (
                id           INT AUTO_INCREMENT PRIMARY KEY,
                name         VARCHAR(200) NOT NULL,
                country      VARCHAR(100),
                image_url    VARCHAR(500),
                description  TEXT,
                programs     TEXT,
                ranking      VARCHAR(100),
                link_url     VARCHAR(500),
                sort_order   INT DEFAULT 0,
                is_active    BOOLEAN DEFAULT TRUE,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        )

        # Leads table (contact form inquiries)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                name        VARCHAR(150) NOT NULL,
                phone       VARCHAR(50) NOT NULL,
                email       VARCHAR(255),
                country     VARCHAR(100),
                message     TEXT,
                status      VARCHAR(30) DEFAULT 'new',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        )

        # Students CRM table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id                  INT AUTO_INCREMENT PRIMARY KEY,
                email               VARCHAR(255) UNIQUE NOT NULL,
                password_hash       VARCHAR(255) NULL,
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
                otp_expires_at      TIMESTAMP NULL DEFAULT NULL,
                approved_at         TIMESTAMP NULL DEFAULT NULL,
                notes               TEXT,
                created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        )

        # Add OTP and verification columns if upgrading existing table
        add_column_if_not_exists(cur, "students", "email_verified", "BOOLEAN DEFAULT FALSE")
        add_column_if_not_exists(cur, "students", "otp_code", "VARCHAR(10)")
        add_column_if_not_exists(cur, "students", "otp_expires_at", "TIMESTAMP NULL DEFAULT NULL")
        add_column_if_not_exists(cur, "students", "approved_at", "TIMESTAMP NULL DEFAULT NULL")

        # Student Documents table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS student_documents (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                student_id      INT NOT NULL,
                doc_type        VARCHAR(50) NOT NULL,
                title           VARCHAR(200) NOT NULL,
                file_url        VARCHAR(1000) NOT NULL,
                file_name       VARCHAR(255),
                file_size       VARCHAR(50),
                status          VARCHAR(30) DEFAULT 'pending',
                admin_feedback  TEXT,
                uploaded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        )

        # Student University Applications table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS student_applications (
                id                  INT AUTO_INCREMENT PRIMARY KEY,
                student_id          INT NOT NULL,
                university_name     VARCHAR(255) NOT NULL,
                country             VARCHAR(100),
                program_name        VARCHAR(255),
                intake_semester     VARCHAR(100),
                status              VARCHAR(50) DEFAULT 'Draft',
                portal_url          VARCHAR(1000),
                application_id      VARCHAR(100),
                notes               TEXT,
                created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        )

        conn.commit()
        cur.close()
        conn.close()
        print("✅ [MySQL init_db] All database tables created & verified successfully!")
    except Exception as e:
        print(f"⚠️ [MySQL init_db Error/Warning]: {e}")
