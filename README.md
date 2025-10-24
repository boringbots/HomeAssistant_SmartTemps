# Curve Control Energy Optimizer for Home Assistant

**Intelligent HVAC scheduling that reduces cost using time-of-use electricity rates.**

Curve Control automatically optimizes your air conditioning schedule to run during cheaper electricity rate periods while maintaining your comfort. The system learns your home's thermal characteristics over time and gets smarter every day.

---

## Features

- **Smart Temperature Scheduling** - Optimizes HVAC usage based on user preferences and electricity prices
- **Cost Savings** - Automatically shifts operations to off-peak hours
- **Beautiful Dashboard** - Visual temperature schedule with price indicators
- **Thermal Learning** - Learns your home's heating/cooling rates over time
- **8 Utility Rate Plans** - Supports major TOU plans (SDG&E, ConEd, XCEL, etc.)

---

## Installation

### Method 1: HACS - Coming Soon
*HACS integration is planned for future release.*
You can download it as a custom integration from the HACS add-on today: https://github.com/boringbots/HomeAssistant_SmartTemps.git

### Method 2: Manual Installation

1. **Download the Integration**
   ```bash
   cd /config/custom_components/
   git clone https://github.com/boringbots/HomeAssistant_SmartTemps.git curve_control
   ```

   Or download and extract the `custom_components/curve_control` folder to:
   ```
   /config/custom_components/curve_control/
   ```

2. **Restart Home Assistant**
   - Go to **Settings** → **System** → **Restart**

3. **Add the Integration**
   - Go to **Settings** → **Devices & Services**
   - Click **+ Add Integration**
   - Search for "**Curve Control**"
   - Click to add

4. **Configure Authentication** (Step 1 of 2)
   - **Username**: Choose a username (3-50 characters)
   - **Password**: Secure password (8+ characters)
   - **Email**: Enter email to register OR leave blank to login with existing account
   - Click **Submit**

5. **Configure Preferences** (Step 2 of 2)
   - **Thermostat Entity**: Select your climate entity
   - **Home Size**: Square footage (500-10,000 sq ft)
   - **Target Temperature**: Your comfort temperature (60-85°F)
   - **Location**: Select your utility provider's rate plan
   - **Time Away**: When you typically leave home (e.g., 08:00)
   - **Time Home**: When you typically return home (e.g., 17:00)
   - **Savings Level**: Low / Medium / High (how aggressive to optimize)
   - **Weather Entity**: For weather-aware optimization
   - Click **Submit**

---

## Dashboard Card Setup

The dashboard card file is **automatically copied** to `/config/www/` when you install the integration. You just need to register it and add the card:

#### Step 1: Register the Card Resource

1. Go to **Settings** → **Dashboards**
2. Click **⋮** (three dots menu, top right corner)
3. Select **Resources**
4. Click **+ Add Resource** (bottom right)
5. Fill in **exactly**:
   - **URL**: `/local/curve-control-card.js`
   - **Resource type**: **JavaScript Module**
6. Click **Create**
7. **Hard refresh your browser**:
   - Windows/Linux: `Ctrl+Shift+R`
   - Mac: `Cmd+Shift+R`
8. You may also need to **restart Home Assistant**

#### Step 2: Add Card to Dashboard

1. Go to your dashboard
2. Click **Edit Dashboard** (pencil icon, top right)
   - If this is your first time, click **Take Control** to enable manual editing
3. Click **+ Add Card**
4. Scroll down → **Manual** or **Curve Control Card** under Custom cards
5. Paste this YAML:
   ```yaml
   type: custom:curve-control-card
   entity: sensor.curve_control_energy_optimizer_temperature_schedule_chart
   ```
6. Click **Save**
7. Click **Done**

**That's it!** Your advanced card with temperature graph and interactive controls will appear.

---

## Usage

### Running an Optimization

Click the **Optimize Schedule** button on your dashboard card. This will:
1. Run immediate optimization with current settings
2. Save your preferences to the cloud
3. Enable automatic nightly optimization at midnight

### Automatic Nightly Runs

After your first optimization:
- Your custom schedule is automatically recalculated every night
- Uses updated weather forecast, price changes, and your latest preferences

### Monitoring

The integration creates several helpful sensors:
- `sensor.curve_control_...temperature_schedule_chart` - Main schedule data
- `sensor.curve_control_...cost_savings` - Money saved over 120-day period
- `sensor.curve_control_...co2_avoided` - Environmental impact
- `button.curve_control_optimize_schedule` - Manual optimization trigger

---

## Dashboard Card Features

The dashboard card displays:

- **Temperature Schedule Chart** - 24-hour optimized schedule with price bars
- **Electricity Price Colors**:
  - 🟢 Green = Off-peak (cheapest)
  - 🟡 Yellow = Mid-peak
  - 🔴 Red = On-peak (most expensive)
- **Optimize Button** - Run optimization with one click
- **Savings Stats** - Cost savings, percent savings, CO2 avoided
- **Environmental Impact** - Equivalent cars off the road

---

## 🔧 Configuration Options

### Supported Utility Rate Plans

1. **San Diego Gas & Electric TOU-DR1**
2. **San Diego Gas & Electric TOU-DR2**
3. **San Diego Gas & Electric TOU-DR-P**
4. **San Diego Gas & Electric TOU-ELEC**
5. **San Diego Gas & Electric Standard DR**
6. **New Hampshire TOU Whole House Domestic**
7. **Texas XCEL Time-Of-Use**
8. **NYC ConEdison Residential TOU**

### Savings Levels

- **Low** - Minimal temperature variation, prioritizes comfort
- **Medium** - Balanced comfort and savings
- **High** - Maximum savings, larger temperature swings

---

## 📡 Data Collection & Privacy

### What Data is Collected?

The integration collects:
- Temperature sensor readings every 5 minutes
- HVAC state (heating/cooling/off)
- Target temperature settings

### Why Collect Data?

**Thermal Learning**: Over time, the system learns:
- How fast your home cools down (cooling rate)
- How fast your home heats up (natural drift rate)
- More accurate predictions = better optimization = more savings

### Your Privacy

- ✅ **Secure Authentication**: All data tied to your account only
- ✅ **No Sharing**: Your data is not shared with third parties

---

## Links

- **GitHub Repository**: https://github.com/boringbots/HomeAssistant_SmartTemps
- **Issue Tracker**: https://github.com/boringbots/HomeAssistant_SmartTemps/issues
- **Website**: https://curvecontrol.io 

---

## Tips for Maximum Savings

1. **Set accurate time windows** - Be honest about when you're actually home
2. **Use Medium or High savings level** - Low provides minimal savings
3. **Let it learn** - System gets better after a week of data collection
4. **Check weather integration** - Weather-aware optimization can improve results
5. **Monitor the dashboard** - Watch when AC runs and adjust preferences if needed

---

## Success!

You're now saving with Curve Control! The system will optimize your HVAC automatically.

**Questions?** 

Open an issue on GitHub: https://github.com/boringbots/HomeAssistant_SmartTemps/issues
Or visit: https://curvecontrol.io 
