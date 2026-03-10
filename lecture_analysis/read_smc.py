#!/usr/bin/env python3
"""
Simple SMC reader for CPU temperature and fan speed.
Works with Macs Fan Control and reads directly from SMC.
"""

import subprocess
import json
import sys

def get_smc_value(key):
    """Read SMC key value using ioreg."""
    try:
        # Use ioreg to read SMC values
        cmd = f'ioreg -r -c AppleSMC -d 1 | grep -A 5 "{key}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=2)
        return result.stdout
    except:
        return None

def get_cpu_temp():
    """Get CPU temperature in Celsius."""
    try:
        # Try multiple SMC keys for CPU temperature
        keys = ['TC0P', 'TC0D', 'TC0E', 'TC0F', 'TCAD']
        
        for key in keys:
            output = get_smc_value(key)
            if output and 'temp' in output.lower():
                # Parse temperature value
                # This is a simplified parser, may need adjustment
                lines = output.split('\n')
                for line in lines:
                    if 'value' in line.lower():
                        # Extract numeric value
                        import re
                        match = re.search(r'(\d+\.?\d*)', line)
                        if match:
                            temp = float(match.group(1))
                            if 20 < temp < 120:  # Sanity check
                                return temp
        
        # Fallback: try osx-cpu-temp if available
        result = subprocess.run(['osx-cpu-temp'], capture_output=True, text=True, timeout=1)
        if result.returncode == 0:
            match = re.search(r'(\d+\.?\d*)', result.stdout)
            if match:
                temp = float(match.group(1))
                if temp > 0:
                    return temp
    except:
        pass
    
    return None

def get_fan_speed():
    """Get fan speed in RPM."""
    try:
        # Read fan speed from SMC
        output = get_smc_value('F0Ac')  # Fan 0 actual speed
        if output:
            import re
            match = re.search(r'(\d+)', output)
            if match:
                rpm = int(match.group(1))
                if 0 < rpm < 10000:  # Sanity check
                    return rpm
    except:
        pass
    
    return None

if __name__ == '__main__':
    data = {
        'temp': get_cpu_temp(),
        'fan_rpm': get_fan_speed()
    }
    
    print(json.dumps(data))
