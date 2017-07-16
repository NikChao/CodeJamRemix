drop schema public;
create schema public;

-- TABLES
-- Users
create table public."user" (
    id serial,
    username varchar(255) UNIQUE,
    password varchar(255),
    remember_token varchar(255),
    join_date timestamp
);

-- Problems
create table public."problem" (
    id serial,
    description text,
    points integer,
    test_file_hash varchar(255)
);

-- Tests: Not needed right now will do later

-- Solutions
create table public."solution" (
    id serial,
    user_id integer references public."user" (id),
    problem_id integer references public."problem" (id),
    last_attempt varchar(255),
    solved boolean
);