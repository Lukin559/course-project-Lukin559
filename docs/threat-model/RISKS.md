# Risk Register - Task Tracker

## Обзор
Данный документ содержит реестр рисков безопасности для Task Tracker приложения. Каждый риск оценивается по вероятности (L) и влиянию (I) по шкале 1-5, где Risk = L × I.

## Шкала оценки

### Вероятность (Likelihood)
- **1** - Очень низкая (1-5% в год)
- **2** - Низкая (5-15% в год)
- **3** - Средняя (15-35% в год)
- **4** - Высокая (35-65% в год)
- **5** - Очень высокая (65-100% в год)

### Влияние (Impact)
- **1** - Минимальное (незначительные неудобства)
- **2** - Низкое (временные проблемы)
- **3** - Среднее (заметные проблемы)
- **4** - Высокое (серьезные проблемы)
- **5** - Критическое (критические проблемы)

## Реестр рисков

| ID | Риск | Описание | L | I | Risk | Стратегия | Владелец | Срок | Критерии закрытия |
|----|------|----------|---|---|------|-----------|----------|------|-------------------|
| R001 | Компрометация учетных данных | Кража или подделка учетных данных пользователей | 3 | 5 | 15 | Снизить | Security Team | 30 дней | MFA внедрена, strong password policy |
| R002 | DDoS атака на API | Перегрузка API сервиса атаками | 4 | 4 | 16 | Снизить | DevOps Team | 14 дней | Rate limiting настроен, мониторинг |
| R003 | SQL Injection в Task API | Внедрение malicious SQL через API | 2 | 5 | 10 | Снизить | Backend Team | 21 день | Input validation 100%, параметризованные запросы |
| R004 | XSS атаки через Task данные | Внедрение malicious scripts в задачи | 3 | 4 | 12 | Снизить | Backend Team | 21 день | Output encoding, CSP headers |
| R005 | Перехват HTTP трафика | Man-in-the-middle атаки | 4 | 4 | 16 | Снизить | DevOps Team | 7 дней | TLS 1.3, HSTS headers |
| R006 | Несанкционированный доступ к задачам | Доступ к чужим задачам | 2 | 5 | 10 | Снизить | Backend Team | 14 дней | Authorization checks, access control |
| R007 | Утечка данных задач | Раскрытие конфиденциальных данных | 2 | 5 | 10 | Снизить | Security Team | 30 дней | Encryption at rest, access controls |
| R008 | Подделка JWT токенов | Создание валидных токенов злоумышленником | 1 | 5 | 5 | Снизить | Backend Team | 14 дней | Strong token signing, validation |
| R009 | Отказ от авторства операций | Пользователи отрицают свои действия | 2 | 3 | 6 | Принять | Security Team | 60 дней | Audit logging, immutable logs |
| R010 | Перегрузка системы | Система недоступна из-за нагрузки | 3 | 4 | 12 | Снизить | DevOps Team | 21 день | Load balancing, auto-scaling |
| R011 | Уязвимости в зависимостях | Exploits в используемых библиотеках | 3 | 4 | 12 | Снизить | Backend Team | 7 дней | Dependency scanning, patch management |
| R012 | Недостаточное логирование | Отсутствие аудита критических операций | 2 | 3 | 6 | Снизить | Backend Team | 30 дней | Comprehensive audit logging |

## Детальное описание рисков

### R001: Компрометация учетных данных
- **Описание**: Злоумышленники получают доступ к учетным записям пользователей через краденые пароли, фишинг или brute force атаки
- **Источник**: F1 (Login Request), F7 (Auth Token)
- **Связанные угрозы**: Spoofing, Information Disclosure
- **Связанные NFR**: NFR-004, NFR-011
- **Меры снижения**:
  - Multi-factor authentication (MFA)
  - Strong password policy (минимум 12 символов, сложность)
  - Account lockout после 5 неудачных попыток
  - CAPTCHA для предотвращения автоматических атак
  - Регулярная ротация паролей
- **Мониторинг**: Failed login attempts, unusual login patterns
- **Ответственный**: Security Team
- **Срок**: 30 дней
- **Критерии закрытия**: MFA внедрена для всех пользователей, strong password policy активна

### R002: DDoS атака на API
- **Описание**: Злоумышленники перегружают API сервис большим количеством запросов
- **Источник**: F1, F2, API Gateway
- **Связанные угрозы**: Denial of Service
- **Связанные NFR**: NFR-008, NFR-002
- **Меры снижения**:
  - Rate limiting (200 requests/minute per user)
  - DDoS protection (CloudFlare, AWS Shield)
  - Load balancing с auto-scaling
  - Circuit breakers для защиты downstream сервисов
- **Мониторинг**: Request rate, response times, error rates
- **Ответственный**: DevOps Team
- **Срок**: 14 дней
- **Критерии закрытия**: Rate limiting настроен, мониторинг активен, DDoS protection включена

### R003: SQL Injection в Task API
- **Описание**: Внедрение malicious SQL кода через параметры API
- **Источник**: F2, F9, Task Manager
- **Связанные угрозы**: Tampering, Information Disclosure
- **Связанные NFR**: NFR-005, NFR-010
- **Меры снижения**:
  - Parameterized queries (ORM)
  - Input validation с Pydantic
  - SQL injection scanning в CI/CD
  - Database access controls
- **Мониторинг**: OWASP ZAP scanning, Static analysis
- **Ответственный**: Backend Team
- **Срок**: 21 день
- **Критерии закрытия**: 100% input validation, параметризованные запросы, ZAP baseline в CI

### R004: XSS атаки через Task данные
- **Описание**: Внедрение malicious JavaScript через данные задач
- **Источник**: F2, F9, Task Manager
- **Связанные угрозы**: Tampering, Information Disclosure
- **Связанные NFR**: NFR-005, NFR-012
- **Меры снижения**:
  - Output encoding для всех пользовательских данных
  - Content Security Policy (CSP) headers
  - Input sanitization
  - XSS scanning в CI/CD
- **Мониторинг**: XSS scanning, CSP violation reports
- **Ответственный**: Backend Team
- **Срок**: 21 день
- **Критерии закрытия**: Output encoding реализован, CSP headers настроены

### R005: Перехват HTTP трафика
- **Описание**: Man-in-the-middle атаки для перехвата данных
- **Источник**: F6, F1, F2
- **Связанные угрозы**: Information Disclosure
- **Связанные NFR**: NFR-006
- **Меры снижения**:
  - TLS 1.3 для всех соединений
  - HSTS headers (1 год)
  - Certificate pinning
  - Perfect Forward Secrecy
- **Мониторинг**: SSL Labs testing, Certificate monitoring
- **Ответственный**: DevOps Team
- **Срок**: 7 дней
- **Критерии закрытия**: TLS 1.3 активен, HSTS настроен, SSL Labs A+ rating

### R006: Несанкционированный доступ к задачам
- **Описание**: Пользователи получают доступ к чужим задачам
- **Источник**: F2, Task Manager
- **Связанные угрозы**: Elevation of Privilege
- **Связанные NFR**: NFR-009, NFR-012
- **Меры снижения**:
  - Authorization checks на каждом запросе
  - Resource ownership validation
  - Role-based access control
  - Regular access reviews
- **Мониторинг**: Access control testing, Authorization audits
- **Ответственный**: Backend Team
- **Срок**: 14 дней
- **Критерии закрытия**: Authorization checks реализованы, access control тесты проходят

### R007: Утечка данных задач
- **Описание**: Несанкционированное раскрытие конфиденциальных данных задач
- **Источник**: F12, Task Database
- **Связанные угрозы**: Information Disclosure
- **Связанные NFR**: NFR-012, NFR-006
- **Меры снижения**:
  - Encryption at rest (AES-256)
  - Database access controls
  - Data masking для логов
  - Regular security audits
- **Мониторинг**: Data access logs, Encryption verification
- **Ответственный**: Security Team
- **Срок**: 30 дней
- **Критерии закрытия**: Encryption at rest активна, access controls настроены

### R008: Подделка JWT токенов
- **Описание**: Создание валидных JWT токенов злоумышленником
- **Источник**: F7, Authentication Service
- **Связанные угрозы**: Spoofing, Tampering
- **Связанные NFR**: NFR-004
- **Меры снижения**:
  - Strong token signing (RSA 2048 или HMAC-SHA256)
  - Token validation на каждом запросе
  - Short token lifetime (30 минут)
  - Token revocation mechanism
- **Мониторинг**: Token validation testing, Invalid token attempts
- **Ответственный**: Backend Team
- **Срок**: 14 дней
- **Критерии закрытия**: Strong token signing, validation реализованы

### R009: Отказ от авторства операций
- **Описание**: Пользователи отрицают выполнение операций с задачами
- **Источник**: F15, Audit Logger
- **Связанные угрозы**: Repudiation
- **Связанные NFR**: NFR-007
- **Меры снижения**:
  - Comprehensive audit logging
  - Immutable log storage
  - Digital signatures для критических событий
  - Log integrity verification
- **Мониторинг**: Log analysis, Compliance audits
- **Ответственный**: Security Team
- **Срок**: 60 дней
- **Критерии закрытия**: Audit logging настроен, immutable storage реализован

### R010: Перегрузка системы
- **Описание**: Система становится недоступной из-за высокой нагрузки
- **Источник**: API Gateway, Load Balancer
- **Связанные угрозы**: Denial of Service
- **Связанные NFR**: NFR-002, NFR-008
- **Меры снижения**:
  - Load balancing с auto-scaling
  - Circuit breakers
  - Resource monitoring и alerting
  - Graceful degradation
- **Мониторинг**: System load, Response times, Error rates
- **Ответственный**: DevOps Team
- **Срок**: 21 день
- **Критерии закрытия**: Load balancing настроен, auto-scaling активен

### R011: Уязвимости в зависимостях
- **Описание**: Exploits в используемых библиотеках и фреймворках
- **Источник**: Все компоненты
- **Связанные угрозы**: Tampering, Information Disclosure
- **Связанные NFR**: NFR-010
- **Меры снижения**:
  - Dependency scanning в CI/CD
  - Regular dependency updates
  - Vulnerability monitoring
  - Patch management process
- **Мониторинг**: Snyk, OWASP Dependency Check, Security advisories
- **Ответственный**: Backend Team
- **Срок**: 7 дней
- **Критерии закрытия**: Dependency scanning в CI, patch management процесс

### R012: Недостаточное логирование
- **Описание**: Отсутствие аудита критических операций
- **Источник**: Все компоненты
- **Связанные угрозы**: Repudiation, Information Disclosure
- **Связанные NFR**: NFR-007
- **Меры снижения**:
  - Comprehensive audit logging
  - Log retention policy (90 дней)
  - Log analysis и monitoring
  - Security event correlation
- **Мониторинг**: Log coverage analysis, Security event detection
- **Ответственный**: Backend Team
- **Срок**: 30 дней
- **Критерии закрытия**: Comprehensive audit logging настроен, log retention активна

## Приоритизация рисков

### Критические (Risk ≥ 15)
- R001: Компрометация учетных данных (15)
- R002: DDoS атака на API (16)
- R005: Перехват HTTP трафика (16)

### Высокие (Risk 10-14)
- R003: SQL Injection в Task API (10)
- R004: XSS атаки через Task данные (12)
- R006: Несанкционированный доступ к задачам (10)
- R007: Утечка данных задач (10)
- R010: Перегрузка системы (12)
- R011: Уязвимости в зависимостях (12)

### Средние (Risk 5-9)
- R008: Подделка JWT токенов (5)
- R009: Отказ от авторства операций (6)
- R012: Недостаточное логирование (6)

## Стратегии управления рисками

### Снизить (Mitigate)
- **R001-R012**: Все риски требуют мер снижения
- **Фокус**: Технические контроли, процессы, мониторинг

### Принять (Accept)
- **R009**: Отказ от авторства операций
- **Обоснование**: Низкий риск, высокие затраты на полное устранение

### Избежать (Avoid)
- **Нет рисков**: Все риски можно снизить до приемлемого уровня

### Перенести (Transfer)
- **R002**: DDoS атака (частично через CloudFlare)
- **R005**: Перехват трафика (частично через CDN)

## Связь с NFR из P03

| NFR | Связанные риски | Количество рисков |
|-----|------------------|-------------------|
| NFR-004 | R001, R008 | 2 |
| NFR-005 | R003, R004 | 2 |
| NFR-006 | R005, R007 | 2 |
| NFR-007 | R009, R012 | 2 |
| NFR-008 | R002, R010 | 2 |
| NFR-009 | R006 | 1 |
| NFR-010 | R003, R011 | 2 |
| NFR-011 | R001 | 1 |
| NFR-012 | R004, R006, R007 | 3 |

## План реализации

### Фаза 1 (0-7 дней) - Критические
- R005: Перехват HTTP трафика
- R011: Уязвимости в зависимостях

### Фаза 2 (7-14 дней) - Высокие
- R002: DDoS атака на API
- R006: Несанкционированный доступ к задачам
- R008: Подделка JWT токенов

### Фаза 3 (14-30 дней) - Средние
- R001: Компрометация учетных данных
- R003: SQL Injection в Task API
- R004: XSS атаки через Task данные
- R007: Утечка данных задач
- R010: Перегрузка системы
- R012: Недостаточное логирование

### Фаза 4 (30-60 дней) - Долгосрочные
- R009: Отказ от авторства операций
