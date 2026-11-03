-- Run ONCE as the PostgreSQL superuser (usually "postgres"):
--   psql -U postgres -f scripts/create_db.sql
--
-- Creates a LEAST-PRIVILEGE login for the app: not a superuser, cannot create
-- databases or roles. It owns only the two databases below.
-- \password asks for the password interactively, so it never lands in a file or
-- in your shell history.

CREATE ROLE fooddelivery_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
\password fooddelivery_app

CREATE DATABASE fooddelivery OWNER fooddelivery_app;
CREATE DATABASE fooddelivery_test OWNER fooddelivery_app;
