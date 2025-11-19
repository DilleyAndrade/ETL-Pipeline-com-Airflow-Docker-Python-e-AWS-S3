from datetime import datetime, timedelta, date
from airflow.decorators import dag, task
from dotenv import load_dotenv
import pandas as pd
import requests
import boto3
import os

load_dotenv()

session = boto3.Session(
  aws_access_key_id = os.getenv('aws_access_key_id'),
  aws_secret_access_key = os.getenv('aws_secret_access_key'),
  region_name = os.getenv('aws_region')
)

s3 = session.client('s3')

default_args = {
  'owner': f'{'user_name'}',
  'email': [f'{os.getenv('user_email')}'],
  'retry': 3,
  'retry_delay': timedelta(minutes = 5)
}

@dag(
  dag_id = 'etl_pipeline',
  schedule = None,
  start_date = datetime(2025, 10, 20),
  end_date = datetime(2025, 10, 29),
  catchup = None,
  default_args = default_args
)
def etl_pipeline():
  directory = os.listdir('data')
  @task
  def etl_users():

    #Extract
    try:
      url_users = 'https://fakestoreapi.com/users'
      response = requests.get(url_users)
      print('Connection https://fakestoreapi.com/users success')
    except Exception as e:
      raise ValueError(f'Failed to connect with https://fakestoreapi.com/users. ERROR:{e}')

    #Transform
    data = response.json()
    df = pd.DataFrame(data)
    df['user_id'] = df['id']
    df['first_name'] = df['name'].apply(lambda x: x['firstname'])
    df['last_name'] = df['name'].apply(lambda x: x['lastname'])
    df['user_name'] = df['username']
    df['city'] = df['address'].apply(lambda x: x['city'])
    df['street'] = df['address'].apply(lambda x: x['street'])
    df['number'] = df['address'].apply(lambda x: x['number'])
    df['zipcode'] = df['address'].apply(lambda x: x['zipcode'])
    df['created_at'] = datetime.now()
    df['updated_at'] = datetime.now()

    df = df[[
      'user_id', 'first_name', 'last_name', 'user_name', 'email', 
      'password', 'phone', 'city', 'street', 'number', 'zipcode', 
      'created_at', 'updated_at'
    ]]

    #Load
    try:
      df.to_parquet(f'data/{date.today()}-USER.parquet', compression='snappy')
      print('Users parquet file saved success!')
    except Exception as e:
      raise ValueError(f'Failed to save parquet file users. ERROR:{e}')
  
  @task
  def etl_products():
    #Extract
    try:
      url_prod = 'https://fakestoreapi.com/products'
      response = requests.get(url_prod)
      print('Connection https://fakestoreapi.com/users success')
    except Exception as e:
      raise ValueError(f'Failed to connect with https://fakestoreapi.com/products. ERROR:{e}')

    #Transform
    data = response.json()
    df = pd.DataFrame(data)
    df = df.rename(columns={'id': 'product_id', 'title' : 'product_name'})
    df['created_at'] = datetime.now()
    df['updated_at'] = datetime.now()
    df = df[['product_id','product_name', 'price', 'description', 'category', 'image', 'created_at', 'updated_at']]

    #Load
    try:
      df.to_parquet(f'data/{date.today()}-PRODUCT.parquet', compression='snappy', index=False)
    except Exception as e:
      raise ValueError(f'Connection https://fakestoreapi.com/products failed. ERROR: {e}')

  @task
  def etl_carts():
    to_dataframe = {'cart_id':[], 'user_id':[],'date':[],'product_id':[], 'quantity':[]}

    try:
      url_carts ='https://fakestoreapi.com/carts'
      response = requests.get(url_carts)
    except Exception as e:
      raise ValueError(f'Failed to connect with https://fakestoreapi.com/carts. ERROR:{e}')
    data = response.json()
    for line in data:
      for prod_quan in line['products']:
      
        to_dataframe['cart_id'].append(line['id'])
        to_dataframe['user_id'].append(line['userId'])
        to_dataframe['date'].append(line['date'])
        to_dataframe['product_id'].append(prod_quan['productId'])
        to_dataframe['quantity'].append(prod_quan['quantity'])

    df = pd.DataFrame(to_dataframe)
    df['created_at'] = datetime.today()
    df['updated_at'] = datetime.today()
    try:
      df.to_parquet(f'data/{date.today()}-CARTS', compression='snappy', index=False)
      print('CARTS parquet file saved')
    except Exception as e:
      raise ValueError(f'Failed to seve CARTS parquet. ERROR: {e}')

  @task
  def send_to_s3():
    for file in directory:
      try:
        s3.upload_file(f'data/{file}', os.getenv('bucket_name'), f'{date.today()}/{file}')
        print(os.getenv('bucket_name'))
        print(f'File {file} sended to S3 success')
      except Exception as e:
        raise ValueError(f'Error to send {file} to S3. ERROR: {e}')
  #A próxima etapa não seria necessária, poderia enviar os arquivos direto para o S3
  #sem a necessidade de criar arquivos locais, mas serviu como prática para a
  #manipulação de arquivos armazenados em disco 
  @task(trigger_rule='all_success')
  def delete_local_files():
    for file in directory:
      try:
        os.remove(f'data/{file}')
      except Exception as e:
        raise ValueError(f'Error to delete {file} in data. ERROR: {e}')


  etl_users() >> etl_products() >> etl_carts() >> send_to_s3() >> delete_local_files()

pipeline = etl_pipeline()