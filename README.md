项目安装步骤：
git clone git@github.com:winkey11111/program-two.git
		
cd back
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt

cd front
npm install
npm run dev
