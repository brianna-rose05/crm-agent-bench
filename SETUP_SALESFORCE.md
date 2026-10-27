# One-time Salesforce setup (about 20 minutes)

Do this once in your Developer Edition org before running `reset.py`.

## 1. Add a "Benchmark ID" field to four objects

The ID lets the graders find planted records (like "the Northwind renewal") after
every reset, because Salesforce's own record IDs change each time.

For each of **Account**, **Contact**, **Opportunity** and **Activity**:

1. Setup → **Object Manager** → click the object.
2. **Fields & Relationships** → **New**.
3. Choose **Text** → Next.
4. Field Label: `Benchmark ID`, Length: `20`. Check **External ID**. The Field Name fills
   in as `Benchmark_ID`. → Next.
5. Field-level security: make sure **Visible** is checked for **System Administrator**. → Next.
6. Leave page layouts checked → **Save**.

"Activity" is the object that holds Tasks and Events. Adding the field there adds it to Tasks.

## 2. Add a "Sales Rep" picklist to two objects

Developer Edition allows only a couple of real users, so the fake reps live in a
picklist instead.

For each of **Opportunity** and **Activity**:

1. Object Manager → the object → **Fields & Relationships** → **New**.
2. Choose **Picklist** → Next.
3. Field Label: `Sales Rep`.
4. Choose "Enter values, with each value separated by a new line" and enter:
   ```
   Dana
   Luis
   Priya
   Enterprise Team
   ```
5. Check **Restrict picklist to the values defined in the value set**. → Next.
6. Make sure **Visible** is checked for System Administrator → Next → **Save**.

## 3. Turn off the standard duplicate rules

Salesforce has built-in rules that warn or block when a duplicate contact or
account is saved. The benchmark plants duplicates on purpose and tests whether
the *agent* handles them, so these rules have to be off.

1. Setup → search **Duplicate Rules**.
2. Open **Standard Account Duplicate Rule** → **Deactivate**.
3. Open **Standard Contact Duplicate Rule** → **Deactivate**.
4. If a **Standard Lead Duplicate Rule** exists, you can leave it; leads aren't used.

## 4. Load the data

```bash
python reset.py
```

It shows what it will delete, asks you to type `RESET`, then loads 17 accounts,
29 contacts, 43 opportunities and 126 tasks. If a field is missing, it tells you
which one.

To check, open the **Opportunities** tab in Salesforce and switch the list view
to **All Opportunities**.
