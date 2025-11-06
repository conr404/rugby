/**
 * Rugby Team Allocator - Google Apps Script Integration
 * 
 * This script integrates with the Cloud Function to run team allocation
 * directly from Google Sheets.
 */

// Configuration
const CLOUD_FUNCTION_URL = 'YOUR_CLOUD_FUNCTION_URL_HERE'; // Replace with your Cloud Function URL
const SOURCE_SHEET_NAME = 'Team_sheet';
const OUTPUT_SHEET_NAME = '1st_Sort_Output_v2';

/**
 * Creates custom menu when spreadsheet opens
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('Team Allocation')
    .addItem('Run Team Allocation', 'runTeamAllocation')
    .addItem('Test Connection', 'testConnection')
    .addSeparator()
    .addItem('View Logs', 'viewLogs')
    .addToUi();
}

/**
 * Main function: Runs team allocation via Cloud Function
 */
function runTeamAllocation() {
  const ui = SpreadsheetApp.getUi();
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  try {
    // Show progress
    ui.alert('Starting team allocation...');
    
    // 1. Get source sheet
    let sourceSheet;
    try {
      sourceSheet = ss.getSheetByName(SOURCE_SHEET_NAME);
      if (!sourceSheet) {
        ui.alert('Error: Sheet "' + SOURCE_SHEET_NAME + '" not found. Please check the sheet name.');
        return;
      }
    } catch (e) {
      ui.alert('Error: Could not access source sheet. ' + e.toString());
      return;
    }
    
    // 2. Extract data from sheet
    const lastRow = sourceSheet.getLastRow();
    const lastCol = sourceSheet.getLastColumn();
    
    if (lastRow < 2) {
      ui.alert('Error: No data found in source sheet. Please ensure there is at least a header row and one data row.');
      return;
    }
    
    // Get headers
    const headers = sourceSheet.getRange(1, 1, 1, lastCol).getValues()[0];
    Logger.log('Headers: ' + headers);
    
    // Get data
    const dataRange = sourceSheet.getRange(2, 1, lastRow - 1, lastCol);
    const data = dataRange.getValues();
    
    // Validate data
    if (!data || data.length === 0) {
      ui.alert('Error: No data rows found');
      return;
    }
    
    Logger.log('Found ' + data.length + ' data rows');
    
    // 3. Package data for API
    const players = [];
    for (let i = 0; i < data.length; i++) {
      const row = data[i];
      const player = {};
      
      // Map columns to player object
      headers.forEach(function(header, colIdx) {
        const headerKey = String(header).trim().toLowerCase().replace(/\s+/g, '_');
        let value = row[colIdx];
        
        // Handle different data types
        if (value === null || value === undefined || value === '') {
          // Set defaults based on column
          if (headerKey === 'available') {
            value = 0;
          } else if (headerKey === 'istentpole') {
            value = false;
          } else if (headerKey === 'tier') {
            value = 2;
          } else if (headerKey === 'pod') {
            value = 'Unknown';
          } else {
            value = '';
          }
        }
        
        player[headerKey] = value;
      });
      
      // Ensure required fields exist
      if (!player.hasOwnProperty('key')) {
        player.key = '';
      }
      if (!player.hasOwnProperty('available')) {
        player.available = 0;
      }
      if (!player.hasOwnProperty('istentpole')) {
        player.istentpole = false;
      }
      if (!player.hasOwnProperty('pairedwith')) {
        player.pairedwith = '';
      }
      if (!player.hasOwnProperty('tier')) {
        player.tier = 2;
      }
      if (!player.hasOwnProperty('coach')) {
        player.coach = '';
      }
      if (!player.hasOwnProperty('pod')) {
        player.pod = 'Unknown';
      }
      
      // Only include players with a key
      if (player.key && String(player.key).trim() !== '') {
        players.push(player);
      }
    }
    
    if (players.length === 0) {
      ui.alert('Error: No valid players found. Please ensure the "key" column has player names.');
      return;
    }
    
    Logger.log('Sending ' + players.length + ' players to Cloud Function');
    
    // 4. Get secure OIDC token
    const token = ScriptApp.getIdentityToken(CLOUD_FUNCTION_URL);
    
    if (!token) {
      ui.alert('Error: Could not obtain authentication token. Please check your Cloud Function URL and IAM permissions.');
      return;
    }
    
    // 5. Construct request
    const payload = {
      'players': players
    };
    
    const options = {
      'method': 'post',
      'contentType': 'application/json',
      'payload': JSON.stringify(payload),
      'headers': {
        'Authorization': 'Bearer ' + token
      },
      'muteHttpExceptions': true
    };
    
    // 6. Call Cloud Function
    Logger.log('Calling Cloud Function: ' + CLOUD_FUNCTION_URL);
    const response = UrlFetchApp.fetch(CLOUD_FUNCTION_URL, options);
    const responseCode = response.getResponseCode();
    const responseText = response.getContentText();
    
    Logger.log('Response code: ' + responseCode);
    Logger.log('Response: ' + responseText);
    
    // 7. Handle response
    if (responseCode !== 200) {
      let errorMsg = 'HTTP ' + responseCode;
      try {
        const errorData = JSON.parse(responseText);
        errorMsg += ': ' + (errorData.error || responseText);
      } catch (e) {
        errorMsg += ': ' + responseText;
      }
      ui.alert('Error: ' + errorMsg);
      return;
    }
    
    let responseData;
    try {
      responseData = JSON.parse(responseText);
    } catch (e) {
      ui.alert('Error: Could not parse response from Cloud Function. ' + e.toString());
      return;
    }
    
    if (!responseData.success) {
      ui.alert('Error: ' + (responseData.error || 'Unknown error'));
      return;
    }
    
    // 8. Write results back to sheet
    const allocations = responseData.data.allocations;
    
    // Get or create output sheet
    let outputSheet = ss.getSheetByName(OUTPUT_SHEET_NAME);
    if (!outputSheet) {
      outputSheet = ss.insertSheet(OUTPUT_SHEET_NAME);
    } else {
      outputSheet.clear();
    }
    
    // Write headers
    const outputHeaders = ['key', 'team', 'available', 'pod', 'tier'];
    outputSheet.getRange(1, 1, 1, outputHeaders.length).setValues([outputHeaders]);
    
    // Write data
    const outputData = allocations.map(function(allocation) {
      return [
        allocation.key,
        allocation.team,
        allocation.available,
        allocation.pod,
        allocation.tier
      ];
    });
    
    if (outputData.length > 0) {
      outputSheet.getRange(2, 1, outputData.length, outputHeaders.length).setValues(outputData);
    }
    
    // Format header row
    const headerRange = outputSheet.getRange(1, 1, 1, outputHeaders.length);
    headerRange.setFontWeight('bold');
    headerRange.setBackground('#4285f4');
    headerRange.setFontColor('#ffffff');
    
    // Auto-resize columns
    for (let i = 1; i <= outputHeaders.length; i++) {
      outputSheet.autoResizeColumn(i);
    }
    
    // Show success message
    const summary = responseData.data;
    ui.alert('Team allocation completed successfully!\n\n' +
             'Total players: ' + summary.total_players + '\n' +
             'Available players: ' + summary.available_players + '\n' +
             'Assigned players: ' + summary.assigned_players + '\n\n' +
             'Results written to "' + OUTPUT_SHEET_NAME + '" sheet.');
    
  } catch (error) {
    Logger.log('Error: ' + error.toString());
    Logger.log('Stack: ' + error.stack);
    ui.alert('Error: ' + error.toString());
  }
}

/**
 * Test connection to Cloud Function
 */
function testConnection() {
  const ui = SpreadsheetApp.getUi();
  
  if (CLOUD_FUNCTION_URL === 'YOUR_CLOUD_FUNCTION_URL_HERE') {
    ui.alert('Error: Cloud Function URL not configured. Please update CLOUD_FUNCTION_URL in the script.');
    return;
  }
  
  try {
    const token = ScriptApp.getIdentityToken(CLOUD_FUNCTION_URL);
    
    if (!token) {
      ui.alert('Error: Could not obtain authentication token.');
      return;
    }
    
    const options = {
      'method': 'get',
      'headers': {
        'Authorization': 'Bearer ' + token
      },
      'muteHttpExceptions': true
    };
    
    const response = UrlFetchApp.fetch(CLOUD_FUNCTION_URL, options);
    const code = response.getResponseCode();
    
    if (code === 200 || code === 405) { // 405 = method not allowed (but function exists)
      ui.alert('Connection successful! Cloud Function is accessible.\n\n' +
               'Function URL: ' + CLOUD_FUNCTION_URL + '\n' +
               'Response code: ' + code);
    } else {
      ui.alert('Connection failed.\n\n' +
               'Function URL: ' + CLOUD_FUNCTION_URL + '\n' +
               'Response code: ' + code + '\n' +
               'Response: ' + response.getContentText());
    }
  } catch (error) {
    ui.alert('Error: ' + error.toString());
  }
}

/**
 * View execution logs
 */
function viewLogs() {
  const ui = SpreadsheetApp.getUi();
  const logs = Logger.getLog();
  
  if (!logs || logs.trim() === '') {
    ui.alert('No logs available. Run the allocation first to generate logs.');
    return;
  }
  
  // Show last 2000 characters (UI alert limit)
  const displayLogs = logs.length > 2000 ? '...' + logs.slice(-2000) : logs;
  ui.alert('Recent logs:\n\n' + displayLogs);
}

