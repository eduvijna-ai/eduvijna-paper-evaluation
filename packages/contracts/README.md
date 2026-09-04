# Shared contracts

This package contains the OpenAPI document and JSON Schemas shared by EduVijna
services and clients.

- **Cursor A** owns backend implementation and API/contract alignment.
- **Cursor B** consumes these contracts in the web application.

Run `npm install` once in this directory, then `npm run validate` to parse every
schema and verify the required OpenAPI operations.
