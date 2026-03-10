from pydub import AudioSegment
import sys
import json
import os

def convert_audio(input_path, output_path, bitrate):
    try:
        if not os.path.exists(input_path):
            return {"status": "error", "error": f"Input file not found: {input_path}"}
            
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            
        audio = AudioSegment.from_file(input_path)
        
        # Check if bitrate is VBR level (0-9) or standard bitrate string
        if bitrate.startswith("v"):
            # VBR mode: v0, v1, ..., v9
            v_level = bitrate[1:]
            audio.export(output_path, format="mp3", parameters=["-q:a", v_level])
        else:
            # CBR mode
            audio.export(output_path, format="mp3", bitrate=f"{bitrate}k")
        
        new_size = os.path.getsize(output_path)
        
        return {
            "status": "success",
            "output_path": output_path,
            "new_size": new_size
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(json.dumps({"status": "error", "error": "Usage: convert_audio.py <input> <output> <bitrate>"}))
        sys.exit(1)
        
    result = convert_audio(sys.argv[1], sys.argv[2], sys.argv[3])
    print(json.dumps(result))
