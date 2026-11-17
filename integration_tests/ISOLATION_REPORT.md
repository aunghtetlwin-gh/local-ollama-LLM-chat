# Conversation isolation verification — 2026-10-30

## Scope and conclusion

No cross-user conversation authorization bypass was found in the reviewed source or disposable PostgreSQL tests. This verifies the checked-out application, not the running deployment. No changes were made to server.py, auth.py, database.py, existing tests, or existing Git changes.

## Authentication and authorization

`auth.py` hashes account passwords with Argon2id. Registration/login issue a random opaque session cookie; PostgreSQL stores its SHA-256 digest and expiry. `optional_user` joins a valid, unexpired session to its user. `require_user` returns 401 when authentication is missing/invalid/expired and fails closed with 503 on database failure. `require_chat_user` also requires ownership migration version 2 before allowing chat access.

Every conversation route uses `Depends(require_chat_user)`. Ownership comes from the resolved session's user ID, never the request JSON. `ChatRequest` has no user_id field; extra JSON fields are ignored. Queries use bound parameters.

| Operation | Endpoint | Ownership enforcement |
| --- | --- | --- |
| Create | POST /chat without conversation_id | Inserts conversations.user_id from authenticated user |
| List | GET /conversations | WHERE user_id = authenticated user |
| Read conversation | GET /conversations/{conversation_id} | WHERE id = requested ID AND user_id = authenticated user; otherwise 404 |
| Read messages | Same GET endpoint; no separate message route | Parent ownership check, plus EXISTS matching the message's parent and authenticated owner |
| Continue | POST /chat with conversation_id | Checks ID and owner before writes or Ollama; message insertion uses owner-scoped INSERT SELECT; history retrieval also verifies owner |
| Delete | DELETE /conversations/{conversation_id} | Owner-scoped DELETE RETURNING; otherwise 404; message deletion uses the parent FK cascade |

`save_message` independently checks ownership for both user and assistant writes and for the timestamp update. `get_conversation_messages` independently scopes history access. Foreign and nonexistent IDs return the same 404 response. No endpoint exposes owner reassignment. The home page redirects anonymous visitors to login; public registration/login/health routes are intentionally not subject to the conversation API's 401 behavior.

Migration 001 creates users and sessions. Migration 002 adds a non-null conversation owner FK and owner/update index. Existing history is assigned to a selected registered account; multiple accounts require an explicit owner. That administrative assignment needs careful review and is not an automatic reconstruction of historical ownership. Messages inherit ownership through their parent conversation.

## Safe test infrastructure

`test_postgres_isolation.py` creates a fresh PostgreSQL 14 cluster under a private temporary directory. It uses a separate bootstrap role and generated test-only password, SCRAM local authentication, a private Unix socket, and no TCP listener. It accepts no existing database URL and has no fallback to the application database. `.env` loading is suppressed before application imports; all database entrypoints are replaced, and unapproved psycopg connections are blocked. Only synthetic accounts and messages are used.

The baseline conversations/messages schema is reproduced from README.md; both real SQL migration files execute in PostgreSQL. The two registered accounts are researcher_a@example.test and researcher_b@example.test. FastAPI runs through TestClient, and Ollama is replaced with an in-memory streaming response. No inference occurs. Teardown stops only the newly created cluster and removes its temporary files.

Dependencies were installed into /tmp/conversation-isolation-tools, leaving the application's environment unchanged. The sandbox could not start the temporary PostgreSQL server; an approved run outside the sandbox succeeded. No existing PostgreSQL or FastAPI service was restarted, and no existing database was queried or modified. No existing passwords, secrets, backups, or .env contents were read or printed.

## Actual PostgreSQL results

Command: `/tmp/conversation-isolation-tools/bin/python -m pytest integration_tests/test_postgres_isolation.py -q --tb=short`

Result: **11 passed in 1.22 seconds**, with one TestClient/httpx deprecation warning. Ten parameterized tests cover anonymous and invalid-cookie access; one end-to-end test contains the following ownership assertions:

- A creates, lists, reads messages, continues, and deletes its own conversation.
- B's list excludes A's conversation, including with a forged user_id query parameter.
- B cannot read A's conversation/messages, continue it, or delete it: 404.
- Rejected operations do not alter A's conversation, messages, or timestamps and never invoke the Ollama stub.
- Real foreign IDs, nonexistent IDs, zero, and negative IDs cannot bypass ownership.
- Forged user_id JSON during creation and continuation does not change ownership; database rows confirm this for both accounts.
- Internal message read/write helpers deny cross-user access.
- A also cannot read B's conversation; deleting A's conversation cascades only its messages and preserves B's conversation.
- Anonymous and invalid-session requests return 401 for list, read, delete, creation, and continuation.

## Remaining limitations

- The schema does not enable row-level security. Isolation depends on application queries; database administrators and privileged database credentials are outside this guarantee. The disposable test role is a bootstrap superuser, so this test does not validate deployment role privileges.
- Deployment schema, configuration, TLS, network exposure, and running code were deliberately not inspected through the production database. Tests use newly installed dependencies, not a verified copy of deployed dependency versions.
- Secure cookies default to false in source. HTTPS and secure-cookie configuration must be verified separately; stolen valid sessions act as their owner. HttpOnly/SameSite=Lax help but do not establish protection against every XSS/CSRF scenario.
- No login throttling is apparent in auth.py. Account-abuse controls were not tested.
- Raw PostgreSQL errors are printed by chat handlers and may contain submitted data. Log access and sanitization remain separate confidentiality concerns.
- Race conditions, session revocation during an active stream, real Ollama behavior, backup isolation, and shared-host administrators are outside these tests.
- Public /health discloses the configured database name, but does not expose conversation data. No direct message endpoint exists to test separately.

## Internship report summary

Multi-user conversation isolation was verified by reviewing session authentication and ownership-scoped SQL, then running integration tests against a disposable PostgreSQL instance with two researcher accounts. All 11 PostgreSQL tests passed. A user could access and manage their own conversations, while another user received 404 responses for unauthorized access attempts. Anonymous requests received 401, and forged conversation IDs or user_id fields did not override authenticated ownership. Production data and services were untouched, and no model inference was performed. The findings support application-level isolation while leaving deployment security and database-level defense in depth for separate verification.

Additional regression results: **35 passed in 0.91 seconds** across tests/test_auth.py, tests/test_conversation_access.py, and tests/test_migrations.py. These existing tests use SQLite/mock SQL, with external services blocked and .env loading suppressed. They cover session expiry/revocation, migration readiness, and database-failure denial in addition to the PostgreSQL checks. The initial sandboxed regression run stalled; the approved run outside the sandbox completed successfully. Both successful suites emitted only the TestClient/httpx deprecation warning.
