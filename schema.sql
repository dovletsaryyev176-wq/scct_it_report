CREATE TABLE programs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    order_date DATE,           
    order_number VARCHAR(100), 
    start_date DATE,           
    end_date DATE,             
    status ENUM('active', 'blocked') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE cities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    status ENUM('active', 'blocked') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE districts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    city_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    status ENUM('active', 'blocked') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE CASCADE
);


CREATE TABLE organizations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    parent_id INT NULL,
    city_id INT NOT NULL,
    district_id INT NOT NULL,
    address TEXT,
    phone VARCHAR(50),
    status ENUM('active', 'blocked') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES organizations(id) ON DELETE SET NULL,
    FOREIGN KEY (city_id) REFERENCES cities(id),
    FOREIGN KEY (district_id) REFERENCES districts(id)
);

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    phone VARCHAR(20) UNIQUE,
    role ENUM('admin', 'user', 'company_user') DEFAULT 'user',
    is_verified TINYINT(1) DEFAULT 0,
    otp_code VARCHAR(6),
    otp_expiry DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

ALTER TABLE users 
ADD COLUMN full_name VARCHAR(255) AFTER username,
ADD COLUMN order_number VARCHAR(100) AFTER phone,
ADD COLUMN order_date DATE AFTER order_number,
ADD COLUMN status ENUM('active', 'blocked') DEFAULT 'active' AFTER role;

CREATE TABLE IF NOT EXISTS user_organizations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    organization_id INT NOT NULL,
    is_main TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
);


CREATE TABLE events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    program_id INT NOT NULL,
    item_number VARCHAR(50),   
    name TEXT NOT NULL,      
    deadline VARCHAR(255),     
    status ENUM('active', 'blocked') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE CASCADE
);

CREATE TABLE event_organizations (
    event_id INT NOT NULL,
    organization_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (event_id, organization_id),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
);

CREATE TABLE event_statuses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    status ENUM('active', 'blocked') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE failure_reasons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    status ENUM('active', 'blocked') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE program_reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    program_id INT NOT NULL,
    report_type ENUM('gündelik', 'hepdeleýin', 'aýlyk', 'çärýeklik', 'ýyllyk') NOT NULL,
    status ENUM('active', 'blocked') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE CASCADE
);

CREATE TABLE reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    organization_id INT NOT NULL,
    event_id INT NOT NULL,
    program_report_id INT NOT NULL, -- Ссылка на правило (ежедневно, ежемесячно и т.д.)
    report_period VARCHAR(50) NOT NULL, -- Значение периода (например, "2026-03" или "2026-Q1")
    status_id INT NOT NULL, -- Из таблицы event_statuses
    failure_reason_id INT NULL, -- Из failure_reasons (если не выполнено)
    description TEXT, -- Текстовый комментарий
    created_user_id INT NOT NULL, -- Кто именно нажал кнопку "Отправить"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (event_id) REFERENCES events(id),
    FOREIGN KEY (program_report_id) REFERENCES program_reports(id),
    FOREIGN KEY (status_id) REFERENCES event_statuses(id),
    FOREIGN KEY (failure_reason_id) REFERENCES failure_reasons(id),
    FOREIGN KEY (created_user_id) REFERENCES users(id),
    
    -- Защита от дублей: одна организация -> одно мероприятие -> один период = один отчет
    UNIQUE KEY unique_report_period (organization_id, event_id, report_period)
);

CREATE TABLE report_files (
    id INT AUTO_INCREMENT PRIMARY KEY,
    report_id INT NOT NULL,
    file_path VARCHAR(500) NOT NULL, -- Путь к файлу на сервере
    original_name VARCHAR(255) NOT NULL, -- Исходное имя файла (для красоты)
    file_type ENUM('document', 'photo') NOT NULL, -- Разделение на док и фото
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
);