# Seed data

Two tenants, so the tenant switcher has something to switch between:

| tenant     | insights                        |
|------------|---------------------------------|
| `catalyst` | all three confirmed insights    |
| `vanta`    | the EV billing insight only, with its own figures |

Both tenants use the business key `ins_003` for the billing insight. That is
deliberate: insight ids are unique *per tenant*, and having the same id mean
different rows for different tenants is the sharpest demonstration that scoping
is real.

Every file is idempotent -- insights upsert on `(tenant_id, insight_id)`, and
child rows are deleted and rewritten per insight. Running the seed twice leaves
the database exactly as running it once did.

Run it:

    set -a; source backend/.env; set +a
    mvn -f backend/pom.xml spring-boot:run -Dspring-boot.run.arguments=--seed

or, equivalently:

    mvn -f backend/pom.xml -Pseed spring-boot:run
