# Test Credentials

## Admin / Owner Account (Cranmore Carpenters)
- Email: factory@maxxdoors.com.au
- Password: Cranmore2026!
- Role: admin
- Company: Cranmore Carpenters (main contractor / project owner)

## Trade Test User (Summerset Plumbing)
- Email: plumbing@maxxdoors.com.au
- Password: Cranmore2026!
- Role: trade
- Company: Summerset Plumbing (sees only Sanitary Visis it is assigned/reviewer/visible-to)

## Project
- Summerset Oakleigh South (real dataset, drawing set 225-MB-CHC)
- Trades/Templates: Skirting, Sanitary, Door, Miscellaneous
- Buildings: RACF (aged care), ILA (independent living apartments), General
- 137 real documents ingested (PDF drawings/schedules/quotes + 1 image)

## Auth Endpoints
- POST /api/auth/register, /api/auth/login, /api/auth/logout
- GET  /api/auth/me ; POST /api/auth/refresh
JWT via httpOnly cookies + Bearer fallback.
