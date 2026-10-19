-- Career tracker schema. Safe to re-run: apply_schema.py runs this whole file
-- and every statement is "if not exists".
--
-- Dates are plain `date`s in America/Chicago, computed in Python and passed in.
-- Nothing here defaults to current_date or now(). The status / kind lists are
-- repeated from app/config.py; change both together.

create table if not exists companies (
    company_id   bigint generated always as identity primary key,
    name         text not null check (btrim(name) <> ''),
    website      text,
    industry     text,
    location     text,
    notes        text,
    created_on   date not null
);
-- One row per company, whatever the capitalisation.
create unique index if not exists companies_name_key on companies (lower(name));

create table if not exists contacts (
    contact_id         bigint generated always as identity primary key,
    company_id         bigint references companies on delete set null,
    name               text not null check (btrim(name) <> ''),
    title              text,
    kind               text check (kind in
                         ('recruiter', 'hiring manager', 'referral', 'colleague', 'network')),
    email              text,
    phone              text,
    linkedin           text,
    notes              text,
    last_contacted_on  date,
    created_on         date not null
);

create table if not exists applications (
    application_id  bigint generated always as identity primary key,
    -- A company with applications cannot be deleted: delete those first.
    company_id      bigint not null references companies on delete restrict,
    role            text not null check (btrim(role) <> ''),
    job_url         text,
    location        text,
    work_mode       text check (work_mode in ('onsite', 'hybrid', 'remote')),
    salary_min      integer check (salary_min >= 0),
    salary_max      integer check (salary_max >= 0),
    source          text,
    status          text not null check (status in
                      ('saved', 'applied', 'screening', 'interviewing', 'offer',
                       'accepted', 'rejected', 'withdrawn')),
    applied_on      date,
    next_action     text,
    next_action_on  date,
    contact_id      bigint references contacts on delete set null,
    notes           text,
    created_on      date not null,
    check (salary_min is null or salary_max is null or salary_max >= salary_min)
);

-- Every status an application has been in, with the day it changed. The first
-- row is written with the application itself.
create table if not exists application_events (
    event_id        bigint generated always as identity primary key,
    application_id  bigint not null references applications on delete cascade,
    status          text not null check (status in
                      ('saved', 'applied', 'screening', 'interviewing', 'offer',
                       'accepted', 'rejected', 'withdrawn')),
    happened_on     date not null,
    note            text
);
create index if not exists application_events_app on application_events (application_id);

create table if not exists interviews (
    interview_id    bigint generated always as identity primary key,
    application_id  bigint not null references applications on delete cascade,
    scheduled_on    date not null,
    start_time      time,              -- local (Chicago) wall-clock time
    round           text,              -- e.g. "Recruiter screen", "Onsite 2"
    format          text,              -- phone, video, onsite, take-home
    interviewers    text,
    prep_notes      text,
    outcome_notes   text,
    rating          smallint check (rating between 1 and 5)  -- how it went
);
create index if not exists interviews_app on interviews (application_id);

-- The career log: wins, skills, certifications, feedback, things learned.
create table if not exists career_entries (
    entry_id     bigint generated always as identity primary key,
    kind         text not null check (kind in
                   ('win', 'skill', 'certification', 'feedback', 'learning')),
    title        text not null check (btrim(title) <> ''),
    details      text,
    happened_on  date not null,
    tags         text
);

-- Job history, with pay, for salary negotiations and resumes.
create table if not exists positions (
    position_id  bigint generated always as identity primary key,
    employer     text not null check (btrim(employer) <> ''),
    title        text not null check (btrim(title) <> ''),
    started_on   date not null,
    ended_on     date,
    base_salary  integer check (base_salary >= 0),
    bonus        integer check (bonus >= 0),
    other_comp   text,
    notes        text,
    check (ended_on is null or ended_on >= started_on)
);

-- What you're looking for. One row; the daily job-alert review scores every
-- lead against it.
create table if not exists job_profile (
    profile_id     smallint primary key check (profile_id = 1),
    target_roles   text,
    locations      text,
    work_modes     text,              -- e.g. "remote, hybrid"
    min_salary     integer check (min_salary >= 0),
    must_haves     text,
    nice_to_haves  text,
    deal_breakers  text,
    about_me       text,              -- experience and skills, resume-style
    skip_companies text,              -- one per line: the review drops their jobs
    updated_on     date not null
);

-- Jobs found in alert emails, scored for fit. "moved" ones became an
-- application; the same job from several sites is stored once (dedupe_key:
-- company, title and location, lower-cased, punctuation dropped).
create table if not exists job_leads (
    lead_id         bigint generated always as identity primary key,
    source          text not null check (btrim(source) <> ''),
    title           text not null check (btrim(title) <> ''),
    company         text not null check (btrim(company) <> ''),
    location        text,
    work_mode       text check (work_mode in ('onsite', 'hybrid', 'remote')),
    salary_min      integer check (salary_min >= 0),
    salary_max      integer check (salary_max >= 0),
    pay_source      text check (pay_source in ('listed', 'estimated')),  -- null: pay unknown
    pay_note        text,              -- where an estimate came from
    job_url         text,
    posted_on       date,
    found_on        date not null,
    fit_score       numeric(3,1) check (fit_score between 1 and 10),
    fit_detail      jsonb,             -- {"ratings": {category: 1-10}, "deal_breaker": bool}
    fit_reason      text,
    status          text not null check (status in ('new', 'moved', 'dismissed')),
    dismiss_reason  text check (dismiss_reason in ('wrong role', 'location', 'pay', 'company',
                                                   'already applied', 'other')),
    dismissed_on    date,
    application_id  bigint references applications on delete set null,
    dedupe_key      text not null,             -- company|title (logic.lead_key)
    check (salary_min is null or salary_max is null or salary_max >= salary_min)
);
create unique index if not exists job_leads_dedupe on job_leads (dedupe_key);

-- App settings, one row per key: "theme" is "light" or "dark".
create table if not exists settings (
    key    text primary key,
    value  text not null
);
