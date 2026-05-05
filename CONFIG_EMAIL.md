# Email Configuration Setup Guide

## Quick Start

1. **Rename `.env.example` to `.env`** in your project root:
   ```
   copy .env.example .env
   ```

2. **Add your email credentials** to the `.env` file

---

## Option 1: Gmail (Recommended)

### Steps:

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already enabled
3. Generate an **App Password**:
   - Go to [App Passwords](https://myaccount.google.com/apppasswords)
   - Select "Mail" and "Windows Computer"
   - Copy the generated 16-character password

4. Update `.env`:
   ```
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=your-16-char-app-password
   MAIL_DEFAULT_SENDER=your-email@gmail.com
   MAIL_FROM_NAME=Student Dues System
   ```

---

## Option 2: SendGrid

1. Sign up at [SendGrid](https://sendgrid.com)
2. Create an API key from the dashboard
3. Update `.env`:
   ```
   MAIL_SERVER=smtp.sendgrid.net
   MAIL_PORT=587
   MAIL_USERNAME=apikey
   MAIL_PASSWORD=your-sendgrid-api-key
   MAIL_DEFAULT_SENDER=your-verified-email@example.com
   MAIL_FROM_NAME=Student Dues System
   ```

---

## Option 3: Outlook/Hotmail

Update `.env`:
```
MAIL_SERVER=smtp-mail.outlook.com
MAIL_PORT=587
MAIL_USERNAME=your-email@outlook.com
MAIL_PASSWORD=your-password
MAIL_DEFAULT_SENDER=your-email@outlook.com
MAIL_FROM_NAME=Student Dues System
```

---

## Option 4: Yahoo Mail

Update `.env`:
```
MAIL_SERVER=smtp.mail.yahoo.com
MAIL_PORT=587
MAIL_USERNAME=your-email@yahoo.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@yahoo.com
MAIL_FROM_NAME=Student Dues System
```

---

## Testing

After configuration, run the app and test the password reset flow:
1. Go to student login page
2. Click "Forgot password?"
3. Enter matric number and email
4. Click "Send Verification Code"
5. Check your email for the verification code
6. Enter the code and new password to complete reset

---

## Troubleshooting

- **"MAIL_USERNAME or MAIL_PASSWORD is None"**: Check `.env` file exists and is in the project root
- **"Connection refused"**: Verify MAIL_SERVER and MAIL_PORT are correct
- **"Authentication failed"**: Double-check credentials (Gmail requires App Password, not regular password)
- **Email not received**: Check spam/junk folder

---

## Important Security Notes

- **Never commit `.env` to git** - it contains sensitive credentials
- Use environment variables in production, not `.env` files
- For production, set environment variables via your hosting platform (Heroku, AWS, etc.)
