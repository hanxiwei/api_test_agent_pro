[OPEN] localhost:8000 refused connection

## Symptom
- Running generated tests: cannot connect to localhost:8000 (connection refused).

## Hypotheses
1. Mock API server is not running (port 8000 not listening).
2. Mock API server is running but bound to 127.0.0.1 and tests use localhost/IPv6 mismatch.
3. Port 8000 is occupied by another process or blocked, causing server start failure.
4. base_url/config points to wrong host/port (not 8000).

## Evidence to Collect
- Port 8000 listening state (netstat).
- HTTP GET /pets result (status/timeout/refused).
- If listening: process PID info.

## Next Actions
- Verify port 8000 state and HTTP reachability.
- If not running, start mock_api_server.py and retry tests.
