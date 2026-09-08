# Auth Testing Playbook (SiteQA / Cranmore Carpenters)

## Step 1: MongoDB Verification
mongosh
use test_database
db.users.find({role: "admin"}).pretty()
Verify bcrypt hash starts with `$2b$`; index on users.email unique.

## Step 2: API Testing
curl -c cookies.txt -X POST http://localhost:8001/api/auth/login -H "Content-Type: application/json" -d '{"email":"factory@maxxdoors.com.au","password":"Cranmore2026!"}'
curl -b cookies.txt http://localhost:8001/api/auth/me

Login returns user object + sets access_token & refresh_token cookies.
