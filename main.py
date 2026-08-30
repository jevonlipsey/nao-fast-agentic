import subprocess
import time
import sys
import os

### config
USE_MOCK_NAO = True  # set False to connect to the physical robot via the nao conda env

SCRIPTS = [
    'whisper_stt.py',
    'openai_response.py',
]

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    processes = []

    try:
        # Launch standard Python 3 scripts
        for script in SCRIPTS:
            script_path = os.path.join(script_dir, "scripts", script)
            p = subprocess.Popen([sys.executable, script_path], cwd=script_dir)
            processes.append(p)

        # Launch the Actuation layer (Mock or Real Nao)
        if USE_MOCK_NAO:
            nao_mode = 'mock'
            
            # Launch TTS Mock
            script_path = os.path.join(script_dir, "scripts", 'mock_nao.py')
            p_tts = subprocess.Popen([sys.executable, script_path], cwd=script_dir)
            processes.append(p_tts)

            # Launch Vision Mock
            vision_path = os.path.join(script_dir, "scripts", 'mock_vision.py')
            p_vis = subprocess.Popen([sys.executable, vision_path], cwd=script_dir)
            processes.append(p_vis)
        else:
            nao_mode = 'physical'
            
            # Launch TTS
            script_path = os.path.join(script_dir, "scripts", 'nao_tts.py')
            # Use conda run to execute the script in the isolated Python 2.7 environment
            p_tts = subprocess.Popen(
                ["conda", "run", "--no-capture-output", "-n", "nao", "python", script_path],
                cwd=script_dir
            )
            processes.append(p_tts)

            # Launch Vision
            vision_path = os.path.join(script_dir, "scripts", 'nao_vision.py')
            p_vis = subprocess.Popen(
                ["conda", "run", "--no-capture-output", "-n", "nao", "python", vision_path],
                cwd=script_dir
            )
            processes.append(p_vis)

        print(f'[[PIPELINE]]: running  |  nao={nao_mode}\n')

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print('\n[[PIPELINE]]: shutting down...')
        for p in processes:
            try:
                p.kill() # force kill to prevent hanging
            except Exception:
                pass
        for p in processes:
            try:
                p.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass

if __name__ == '__main__':
    main()
