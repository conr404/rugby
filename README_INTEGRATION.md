# Rugby Team Allocator - Google Sheets Integration

This directory contains the Serverless-Hybrid integration for the Rugby Team Allocator, allowing you to run team allocation directly from Google Sheets.

## Architecture

- **Frontend**: Google Apps Script (`gas-integration/Code.gs`)
- **Backend**: Google Cloud Function (`cloud-function/main.py`)
- **Security**: OIDC token authentication with IAM roles

## Setup Instructions

### Step 1: Deploy Cloud Function

1. Navigate to the cloud-function directory:
   ```bash
   cd cloud-function
   ```

2. Deploy the function (for testing with --allow-unauthenticated):
   ```bash
   gcloud functions deploy rugby-team-allocation \
     --gen2 \
     --runtime=python312 \
     --region=us-central1 \
     --source=. \
     --entry-point=team_allocation \
     --trigger-http \
     --allow-unauthenticated \
     --memory=512MB \
     --timeout=540s
   ```

3. Note the function URL from the deployment output:
   ```
   https://us-central1-PROJECT_ID.cloudfunctions.net/rugby-team-allocation
   ```

### Step 2: Configure Security (Production)

1. Get your Apps Script service account:
   - In Google Apps Script editor, run this function:
   ```javascript
   function getServiceAccount() {
     const serviceAccount = ScriptApp.getService().getServiceAccountEmail();
     Logger.log('Service Account: ' + serviceAccount);
     SpreadsheetApp.getUi().alert('Service Account: ' + serviceAccount);
     return serviceAccount;
   }
   ```

2. Redeploy function as private (remove --allow-unauthenticated):
   ```bash
   gcloud functions deploy rugby-team-allocation \
     --gen2 \
     --runtime=python312 \
     --region=us-central1 \
     --source=. \
     --entry-point=team_allocation \
     --trigger-http \
     --memory=512MB \
     --timeout=540s
   ```

3. Grant IAM permission:
   ```bash
   gcloud functions add-iam-policy-binding rugby-team-allocation \
     --region=us-central1 \
     --member="serviceAccount:YOUR_SERVICE_ACCOUNT_EMAIL" \
     --role="roles/cloudfunctions.invoker"
   ```

### Step 3: Set Up Google Apps Script

1. Open your Google Sheet: https://docs.google.com/spreadsheets/d/1uDXAknETFeFvhowST2W85rJbwzf_ND04miXcTkZplX8

2. Go to **Extensions** → **Apps Script**

3. Delete any existing code and paste the contents of `gas-integration/Code.gs`

4. Update the `CLOUD_FUNCTION_URL` constant with your function URL:
   ```javascript
   const CLOUD_FUNCTION_URL = 'https://us-central1-PROJECT_ID.cloudfunctions.net/rugby-team-allocation';
   ```

5. Save the script (Ctrl+S or Cmd+S)

6. Authorize the script:
   - Click the "Run" button (▶) next to any function
   - Review permissions and click "Allow"

### Step 4: Test the Integration

1. Refresh your Google Sheet
2. You should see a new menu: **Team Allocation**
3. Click **Team Allocation** → **Test Connection**
4. If successful, click **Team Allocation** → **Run Team Allocation**

## Usage

1. Ensure your `Team_sheet` worksheet has the required columns:
   - `key` (player name)
   - `available` (1 for available, 0 for not available)
   - `istentpole` (true/false)
   - `pairedwith` (player name to pair with)
   - `tier` (player tier number)
   - `coach` (coach name)
   - `pod` (Red, Blue, Green, or Pink)

2. Click **Team Allocation** → **Run Team Allocation**

3. Results will be written to the `1st_Sort_Output_v2` worksheet

## Troubleshooting

### "Permission denied" error
- Verify IAM binding: `gcloud functions get-iam-policy rugby-team-allocation --region=us-central1`
- Check service account email matches

### "Invalid token" error
- Ensure `CLOUD_FUNCTION_URL` matches your function URL exactly
- Verify OAuth scopes in Apps Script project settings

### "Method not allowed" error
- Verify function accepts POST requests
- Check function is deployed correctly

### No data in output
- Check that `Team_sheet` has data
- Verify column names match expected format
- Check logs: **Team Allocation** → **View Logs**

## Files

- `cloud-function/main.py` - Cloud Function code
- `cloud-function/requirements.txt` - Python dependencies
- `gas-integration/Code.gs` - Google Apps Script code
- `rugby_team_allocator.py` - Original standalone script (for reference)

## Configuration

You can modify team allocation rules in `cloud-function/main.py`:
- `MIN_TEAM_SIZE = 7`
- `MAX_TEAM_SIZE = 9`
- `IDEAL_TEAM_SIZE = 8`
- `COACH_PAIRINGS = []` - Add coach pairings if needed

## Security Notes

- Never commit credentials or service account keys
- Use IAM roles for authentication (not service account keys)
- Deploy functions as private in production
- Use OIDC tokens (ScriptApp.getIdentityToken()) for secure authentication

