1. Create the below files and folders:
.env
and 1 checkpoint folder with 3 subfolders:
```bash
mkdir checkpoints checkpoints/checkpoint1 checkpoints/checkpoint2 checkpoints/checkpoint3

touch .env
```
and make changes to env using the .env.sample

2. Start containers
```bash
docker-compose up -d
```
3. Start Python virtual env
```bash
python3 -m venv venv 
source venv/bin/activate 
```
4. Install packages
```bash
pip install -r requirements.txt

pip install git+https://github.com/dpkp/kafka-python.git
```

5. Create Postgres tables and randomly generate candidates/voter info.
```bash
python main.py
```

6. Randomly generate votes and produce them to Kafka topic
```bash
python voting.py
```

7. Consume vote data from Kafka topic and process data with Spark
```bash
python spark-streaming.py
```

8. Run Streamlit app
```bash
source venv/bin/activate 

streamlit run streamlit-app.py
```

### Spark Port: 4040
### Streamlit Port: 8501