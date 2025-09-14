#!/usr/bin/env python3
"""
Tạo MQL5 script để export data từ MT5
"""

def create_mql5_script_by_daterange(symbol="XAUUSD", timeframe="PERIOD_M15", date_from="2025.01.01", date_to="2025.09.01", output_path="xauusd_export.csv"):
    """Tạo MQL5 script"""
    
    mql5_script = f'''//+------------------------------------------------------------------+
//|                                         XAUDataExport.mq5       |
//|                                Export {symbol} data by date range |
//+------------------------------------------------------------------+

#property script_show_inputs

input string InpSymbol = "{symbol}";                    // Symbol to export
input ENUM_TIMEFRAMES InpTimeframe = {timeframe};      // Timeframe
input string InpDateFrom = "{date_from}";              // Start date (YYYY.MM.DD)
input string InpDateTo = "{date_to}";                  // End date (YYYY.MM.DD)
input string InpFileName = "{output_path}";            // Output filename

//+------------------------------------------------------------------+
//| Convert date string to datetime                                  |
//+------------------------------------------------------------------+
datetime StringToDateTime(string date_str)
{{
    // Parse "YYYY.MM.DD" format
    string parts[];
    if(StringSplit(date_str, '.', parts) != 3)
    {{
        Print("Error: Invalid date format. Expected YYYY.MM.DD, got: ", date_str);
        return 0;
    }}
    
    int year = (int)StringToInteger(parts[0]);
    int month = (int)StringToInteger(parts[1]);
    int day = (int)StringToInteger(parts[2]);
    
    // Validate date components
    if(year < 2000 || year > 2030 || month < 1 || month > 12 || day < 1 || day > 31)
    {{
        Print("Error: Invalid date values in: ", date_str);
        return 0;
    }}
    
    // Create MqlDateTime structure
    MqlDateTime dt;
    dt.year = year;
    dt.mon = month;
    dt.day = day;
    dt.hour = 0;
    dt.min = 0;
    dt.sec = 0;
    
    return StructToTime(dt);
}}

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
{{
    Print("=== STARTING MT5 DATA EXPORT BY DATE RANGE ===");
    Print("Symbol: ", InpSymbol);
    Print("Timeframe: ", EnumToString(InpTimeframe));
    Print("Date From: ", InpDateFrom);
    Print("Date To: ", InpDateTo);
    Print("Output filename: ", InpFileName);
    Print("Files directory: ", TerminalInfoString(TERMINAL_DATA_PATH), "\\\\MQL5\\\\Files\\\\");
    
    // Convert date strings to datetime
    datetime date_from = StringToDateTime(InpDateFrom);
    datetime date_to = StringToDateTime(InpDateTo);
    
    if(date_from == 0 || date_to == 0)
    {{
        Print("ERROR: Failed to parse dates");
        return;
    }}
    
    if(date_from >= date_to)
    {{
        Print("ERROR: Start date must be before end date");
        return;
    }}
    
    Print("Parsed dates successfully:");
    Print("From: ", TimeToString(date_from));
    Print("To: ", TimeToString(date_to));
    
    // Check if symbol exists
    if(!SymbolSelect(InpSymbol, true))
    {{
        Print("ERROR: Symbol ", InpSymbol, " not found or not selected");
        Print("Available symbols in Market Watch:");
        for(int s = 0; s < SymbolsTotal(true); s++)
        {{
            string sym = SymbolName(s, true);
            if(StringFind(sym, "XAU") >= 0 || StringFind(sym, "GOLD") >= 0)
            {{
                Print("  Found gold symbol: ", sym);
            }}
        }}
        return;
    }}
    
    Print("Symbol ", InpSymbol, " selected successfully");
    
    // Open file for writing
    Print("Attempting to create file: ", InpFileName);
    int handle = FileOpen(InpFileName, FILE_WRITE|FILE_CSV);
    if(handle == INVALID_HANDLE)
    {{
        Print("ERROR: Failed to create file: ", InpFileName);
        Print("Error code: ", GetLastError());
        
        // Try simple filename
        string simple_name = "data.csv";
        Print("Trying simple filename: ", simple_name);
        handle = FileOpen(simple_name, FILE_WRITE|FILE_CSV);
        if(handle == INVALID_HANDLE)
        {{
            Print("ERROR: All attempts failed. Error code: ", GetLastError());
            return;
        }}
        else
        {{
            Print("SUCCESS: Created file with simple name: ", simple_name);
        }}
    }}
    else
    {{
        Print("SUCCESS: File created: ", InpFileName);
    }}
    
    // Write CSV header
    FileWrite(handle, "timestamp", "open", "high", "low", "close", "volume");
    Print("CSV header written");
    
    // Get historical data by date range
    Print("Getting historical data from ", TimeToString(date_from), " to ", TimeToString(date_to));
    MqlRates rates[];
    int copied = CopyRates(InpSymbol, InpTimeframe, date_from, date_to, rates);
    
    if(copied <= 0)
    {{
        Print("Error: Failed to get rates for ", InpSymbol, " in date range");
        Print("Error code: ", GetLastError());
        Print("Trying alternative method with larger range...");
        
        // Alternative: get more data and filter
        int estimated_bars = (int)((date_to - date_from) / PeriodSeconds(InpTimeframe)) + 1000;
        if(estimated_bars > 100000) estimated_bars = 100000;
        
        copied = CopyRates(InpSymbol, InpTimeframe, 0, estimated_bars, rates);
        if(copied <= 0)
        {{
            Print("Error: Alternative method also failed. Error code: ", GetLastError());
            FileClose(handle);
            return;
        }}
        
        Print("Got ", copied, " bars with alternative method, will filter by date");
    }}
    else
    {{
        Print("Retrieved ", copied, " bars for ", InpSymbol, " in specified date range");
    }}
    
    // Write data to CSV (filter by date if needed)
    int written_count = 0;
    for(int i = 0; i < copied; i++)
    {{
        datetime bar_time = rates[i].time;
        
        // Skip bars outside our date range
        if(bar_time < date_from || bar_time > date_to)
            continue;
        
        // Convert datetime to time structure
        MqlDateTime dt;
        TimeToStruct(bar_time, dt);
        
        // Format timestamp as YYYY-MM-DD HH:MM:SS
        string timestamp = StringFormat("%04d-%02d-%02d %02d:%02d:%02d",
                                      dt.year,
                                      dt.mon,
                                      dt.day,
                                      dt.hour,
                                      dt.min,
                                      dt.sec);
        
        // Write row to CSV
        FileWrite(handle,
                 timestamp,
                 DoubleToString(rates[i].open, _Digits),
                 DoubleToString(rates[i].high, _Digits),
                 DoubleToString(rates[i].low, _Digits),
                 DoubleToString(rates[i].close, _Digits),
                 IntegerToString(rates[i].tick_volume));
        
        written_count++;
    }}
    
    FileClose(handle);
    
    // Print summary
    Print("Export completed successfully!");
    Print("File: ", InpFileName);
    Print("Total bars processed: ", copied);
    Print("Records written: ", written_count);
    Print("Symbol: ", InpSymbol);
    Print("Timeframe: ", EnumToString(InpTimeframe));
    Print("Date range: ", TimeToString(date_from), " to ", TimeToString(date_to));
    
    if(written_count > 0)
    {{
        // Find first and last written records
        datetime first_time = 0, last_time = 0;
        double last_close = 0;
        
        for(int i = 0; i < copied; i++)
        {{
            datetime bar_time = rates[i].time;
            if(bar_time >= date_from && bar_time <= date_to)
            {{
                if(first_time == 0) first_time = bar_time;
                last_time = bar_time;
                last_close = rates[i].close;
            }}
        }}
        
        Print("First record: ", TimeToString(first_time));
        Print("Last record: ", TimeToString(last_time));
        Print("Latest close: ", DoubleToString(last_close, _Digits));
    }}
}}'''

    return mql5_script

def create_mql5_script_by_bars(symbol="XAUUSD", timeframe="PERIOD_M15", bars=5000, start_date="2025.09.01", output_path="xauusd_export.csv"):
    """Tạo MQL5 script lấy data theo số lượng bars từ start_date lùi về quá khứ"""
    
    mql5_script = f'''//+------------------------------------------------------------------+
//|                                         XAUDataExport.mq5       |
//|                                Export {symbol} data by bars count |
//+------------------------------------------------------------------+

#property script_show_inputs

input string InpSymbol = "{symbol}";                    // Symbol to export
input ENUM_TIMEFRAMES InpTimeframe = {timeframe};      // Timeframe
input int InpBars = {bars};                            // Number of bars
input string InpStartDate = "{start_date}";            // Start date (YYYY.MM.DD) - will go backward from this date
input string InpFileName = "{output_path}";            // Output filename

//+------------------------------------------------------------------+
//| Convert date string to datetime                                  |
//+------------------------------------------------------------------+
datetime StringToDateTime(string date_str)
{{
    // Parse "YYYY.MM.DD" format
    string parts[];
    if(StringSplit(date_str, '.', parts) != 3)
    {{
        Print("Error: Invalid date format. Expected YYYY.MM.DD, got: ", date_str);
        return 0;
    }}
    
    int year = (int)StringToInteger(parts[0]);
    int month = (int)StringToInteger(parts[1]);
    int day = (int)StringToInteger(parts[2]);
    
    // Validate date components
    if(year < 2000 || year > 2030 || month < 1 || month > 12 || day < 1 || day > 31)
    {{
        Print("Error: Invalid date values in: ", date_str);
        return 0;
    }}
    
    // Create MqlDateTime structure for end of day (23:59:59)
    MqlDateTime dt;
    dt.year = year;
    dt.mon = month;
    dt.day = day;
    dt.hour = 23;
    dt.min = 59;
    dt.sec = 59;
    
    return StructToTime(dt);
}}

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
{{
    Print("=== STARTING MT5 DATA EXPORT BY BARS COUNT ===");
    Print("Symbol: ", InpSymbol);
    Print("Timeframe: ", EnumToString(InpTimeframe));
    Print("Bars: ", InpBars);
    Print("Start Date: ", InpStartDate, " (going backward from this date)");
    Print("Output filename: ", InpFileName);
    Print("Files directory: ", TerminalInfoString(TERMINAL_DATA_PATH), "\\\\MQL5\\\\Files\\\\");
    
    // Validate inputs
    if(InpBars <= 0)
    {{
        Print("ERROR: Invalid number of bars");
        return;
    }}
    
    // Convert start date string to datetime
    datetime start_time = StringToDateTime(InpStartDate);
    if(start_time == 0)
    {{
        Print("ERROR: Failed to parse start date");
        return;
    }}
    
    Print("Parsed start date: ", TimeToString(start_time));
    Print("Will get ", InpBars, " bars going backward from this date");
    
    // Check if symbol exists
    if(!SymbolSelect(InpSymbol, true))
    {{
        Print("ERROR: Symbol ", InpSymbol, " not found or not selected");
        Print("Available symbols in Market Watch:");
        for(int s = 0; s < SymbolsTotal(true); s++)
        {{
            string sym = SymbolName(s, true);
            if(StringFind(sym, "XAU") >= 0 || StringFind(sym, "GOLD") >= 0)
            {{
                Print("  Found gold symbol: ", sym);
            }}
        }}
        return;
    }}
    
    Print("Symbol ", InpSymbol, " selected successfully");
    
    // Open file for writing
    Print("Attempting to create file: ", InpFileName);
    int handle = FileOpen(InpFileName, FILE_WRITE|FILE_CSV);
    if(handle == INVALID_HANDLE)
    {{
        Print("ERROR: Failed to create file: ", InpFileName);
        Print("Error code: ", GetLastError());
        
        // Try simple filename
        string simple_name = "data.csv";
        Print("Trying simple filename: ", simple_name);
        handle = FileOpen(simple_name, FILE_WRITE|FILE_CSV);
        if(handle == INVALID_HANDLE)
        {{
            Print("ERROR: All attempts failed. Error code: ", GetLastError());
            return;
        }}
        else
        {{
            Print("SUCCESS: Created file with simple name: ", simple_name);
        }}
    }}
    else
    {{
        Print("SUCCESS: File created: ", InpFileName);
    }}
    
    // Write CSV header
    FileWrite(handle, "timestamp", "open", "high", "low", "close", "volume");
    Print("CSV header written");
    
    // Get historical data by bars count from start_time
    Print("Getting ", InpBars, " bars from ", TimeToString(start_time), " going backward...");
    MqlRates rates[];
    int copied = CopyRates(InpSymbol, InpTimeframe, start_time, InpBars, rates);
    
    if(copied <= 0)
    {{
        Print("Error: Failed to get rates for ", InpSymbol);
        Print("Error code: ", GetLastError());
        Print("Trying alternative method...");
        
        // Alternative: use CopyRates from position 0
        copied = CopyRates(InpSymbol, InpTimeframe, 0, InpBars, rates);
        if(copied <= 0)
        {{
            Print("Error: Alternative method also failed. Error code: ", GetLastError());
            FileClose(handle);
            return;
        }}
        
        Print("Got ", copied, " bars with alternative method");
    }}
    else
    {{
        Print("Retrieved ", copied, " bars for ", InpSymbol);
    }}
    
    // Write data to CSV
    int written_count = 0;
    for(int i = 0; i < copied; i++)
    {{
        datetime bar_time = rates[i].time;
        
        // Convert datetime to time structure
        MqlDateTime dt;
        TimeToStruct(bar_time, dt);
        
        // Format timestamp as YYYY-MM-DD HH:MM:SS
        string timestamp = StringFormat("%04d-%02d-%02d %02d:%02d:%02d",
                                      dt.year,
                                      dt.mon,
                                      dt.day,
                                      dt.hour,
                                      dt.min,
                                      dt.sec);
        
        // Write row to CSV
        FileWrite(handle,
                 timestamp,
                 DoubleToString(rates[i].open, _Digits),
                 DoubleToString(rates[i].high, _Digits),
                 DoubleToString(rates[i].low, _Digits),
                 DoubleToString(rates[i].close, _Digits),
                 IntegerToString(rates[i].tick_volume));
        
        written_count++;
    }}
    
    FileClose(handle);
    
    // Print summary
    Print("Export completed successfully!");
    Print("File: ", InpFileName);
    Print("Total bars processed: ", copied);
    Print("Records written: ", written_count);
    Print("Symbol: ", InpSymbol);
    Print("Timeframe: ", EnumToString(InpTimeframe));
    Print("Start date: ", TimeToString(start_time));
    Print("Bars requested: ", InpBars);
    
    if(written_count > 0)
    {{
        Print("First record: ", TimeToString(rates[0].time));
        Print("Last record: ", TimeToString(rates[copied-1].time));
        Print("Latest close: ", DoubleToString(rates[copied-1].close, _Digits));
    }}
}}'''

    return mql5_script

def main():
    """Tạo MQL5 script với user input"""
    print("🔧 CREATING MQL5 EXPORT SCRIPT")
    print("=" * 40)
    
    # Show options
    print("📋 Choose export method:")
    print("   1. Export by bars count (from a start date going backward)")
    print("   2. Export by date range (from-to dates)")
    print()
    
    while True:
        option = input("🎯 Select option (1 or 2, default: 2): ").strip() or "2"
        if option in ["1", "2"]:
            break
        print("❌ Invalid option. Please choose 1 or 2.")
    
    # Timeframe mapping
    timeframes = {
        "M1": "PERIOD_M1",
        "M5": "PERIOD_M5", 
        "M15": "PERIOD_M15",
        "M30": "PERIOD_M30",
        "H1": "PERIOD_H1",
        "H4": "PERIOD_H4",
        "D1": "PERIOD_D1"
    }
    
    try:
        # Get common inputs
        symbol = input("📊 Symbol (default: XAUUSD): ").strip() or "XAUUSD"
        
        print("⏰ Available timeframes:")
        for key, value in timeframes.items():
            print(f"   {key} = {value}")
        tf_input = input("⏰ Timeframe (M1/M5/M15/M30/H1/H4/D1, default: M15): ").strip().upper() or "M15"
        
        if tf_input not in timeframes:
            print(f"❌ Invalid timeframe. Using M15")
            tf_input = "M15"
        
        timeframe = timeframes[tf_input]
        
        if option == "1":
            # Option 1: Export by bars count
            print()
            print("📊 OPTION 1: Export by bars count")
            print("=" * 30)
            
            bars_input = input("📏 Number of bars (default: 5000): ").strip() or "5000"
            try:
                bars = int(bars_input)
                if bars <= 0 or bars > 100000:
                    print("❌ Invalid bars count. Using 5000")
                    bars = 5000
            except ValueError:
                print("❌ Invalid bars number. Using 5000")
                bars = 5000
            
            start_date_input = input("📅 Start date - will go backward from 23:59 of this date (YYYY.MM.DD, default: 2025.09.01): ").strip() or "2025.09.01"
            
            # Validate date format
            import re
            date_pattern = r'^\d{4}\.\d{2}\.\d{2}$'
            
            if not re.match(date_pattern, start_date_input):
                print("❌ Invalid start date format. Using 2025.09.01")
                start_date_input = "2025.09.01"
            
            # Use simple filename
            output_filename = f"{symbol.lower()}_{tf_input.lower()}_{bars}bars_export.csv"
            
            # Create script
            script_content = create_mql5_script_by_bars(symbol, timeframe, bars, start_date_input, output_filename)
            script_filename = f"{symbol}Export_{tf_input}_{bars}bars.mq5"
            
        else:
            # Option 2: Export by date range
            print()
            print("📅 OPTION 2: Export by date range")
            print("=" * 30)
            
            date_from_input = input("📅 Start date (YYYY.MM.DD, default: 2025.01.01): ").strip() or "2025.01.01"
            date_to_input = input("📅 End date (YYYY.MM.DD, default: 2025.09.01): ").strip() or "2025.09.01"
            
            # Validate date format
            import re
            date_pattern = r'^\d{4}\.\d{2}\.\d{2}$'
            
            if not re.match(date_pattern, date_from_input):
                print("❌ Invalid start date format. Using 2025.01.01")
                date_from_input = "2025.01.01"
                
            if not re.match(date_pattern, date_to_input):
                print("❌ Invalid end date format. Using 2025.09.01")
                date_to_input = "2025.09.01"
            
            # Use simple filename
            output_filename = f"{symbol.lower()}_{tf_input.lower()}_range_export.csv"
            
            # Create script
            script_content = create_mql5_script_by_daterange(symbol, timeframe, date_from_input, date_to_input, output_filename)
            script_filename = f"{symbol}Export_{tf_input}_range.mq5"
        
        # Save file
        with open(script_filename, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        print()
        print("=" * 50)
        print("✅ MQL5 SCRIPT CREATED SUCCESSFULLY!")
        print("=" * 50)
        print(f"📁 Script file: {script_filename}")
        print(f"📊 Symbol: {symbol}")
        print(f"⏰ Timeframe: {tf_input} ({timeframe})")
        
        if option == "1":
            print(f"📏 Bars: {bars:,}")
            print(f"📅 Start date: {start_date_input} (going backward from 23:59)")
            print(f"📤 Output CSV: {output_filename}")
            print()
            print("💡 TIP: Bars count method:")
            print(f"   - Will get {bars:,} bars going backward from {start_date_input} 23:59")
            print("   - Perfect for getting latest X bars of data")
            print("   - Script includes fallback method if date-based method fails")
        else:
            print(f"📅 Date range: {date_from_input} to {date_to_input}")
            print(f"📤 Output CSV: {output_filename}")
            print()
            print("💡 TIP: Date range method:")
            print("   - The script will automatically handle date range filtering")
            print("   - 15M timeframe is perfect for precise intraday analysis")
            print("   - Script includes fallback method if direct date range fails")
        
        print()
        print("📋 NEXT STEPS:")
        print("1. Copy script to MetaEditor")
        print("2. Compile (F7)")
        print("3. Run (F5)")
        print("4. Find CSV in MQL5/Files directory")
        print("5. Copy CSV to project directory")
        print("6. Run: python import_csv_data.py")
        
    except KeyboardInterrupt:
        print("\n⚠️ Operation cancelled by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        # Fallback to defaults
        print("🔄 Using default values...")
        symbol = "XAUUSD"
        timeframe = "PERIOD_M15"
        date_from = "2025.01.01"
        date_to = "2025.09.01"
        output_filename = "xauusd_export.csv"
        
        script_content = create_mql5_script_by_daterange(symbol, timeframe, date_from, date_to, output_filename)
        
        with open("XAUDataExport.mq5", 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        print("✅ Default script created: XAUDataExport.mq5")

if __name__ == "__main__":
    main()