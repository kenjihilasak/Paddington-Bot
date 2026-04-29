# Import Group Members

Use this from the repo root. The local `.env` must point to the target database and bucket.

## 1. Install dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 2. Confirm the target

Check `.env` before importing:

```env
DATABASE_URL=...
BUCKET=...
ENDPOINT=...
ACCESS_KEY_ID=...
SECRET_ACCESS_KEY=...
REGION=auto
```

If `DATABASE_URL` points to Railway, the import will write to Railway.

## 3. Run a dry run

```powershell
.\.venv\Scripts\python.exe scripts\import_group_members.py --csv "G:\My Drive\04_Projects\Luke Bot\contact wsp group\contactos_paddington.csv" --dry-run
```

## 4. Import users and upload photos

```powershell
.\.venv\Scripts\python.exe scripts\import_group_members.py --csv "G:\My Drive\04_Projects\Luke Bot\contact wsp group\contactos_paddington.csv"
```

The script downloads each CSV `photo_url`, uploads it to:

```text
profile-photos/[wa_id].jpg
```

and stores that object key in:

```text
users.profile_photo_source_url
```

## 5. Verify photos in the bucket

If AWS CLI is already configured for the bucket:

```powershell
aws s3 ls s3://$env:BUCKET/profile-photos/ --recursive --endpoint-url $env:ENDPOINT
```

If you want to load bucket variables from `.env` first:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .\scripts\s3_from_env.ps1
aws s3 ls s3://$env:BUCKET/profile-photos/ --recursive --endpoint-url $env:ENDPOINT
```

## 6. Optional: import without uploading photos

```powershell
.\.venv\Scripts\python.exe scripts\import_group_members.py --csv "G:\My Drive\04_Projects\Luke Bot\contact wsp group\contactos_paddington.csv" --no-upload-photos-to-bucket
```

This keeps CSV `photo_url` values in `users.profile_photo_source_url`.
