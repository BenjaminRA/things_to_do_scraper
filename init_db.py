import os
from datetime import datetime
from pymongo import InsertOne, DeleteMany, ReplaceOne, UpdateOne
import mysql.connector
from db.mongodb import get_client

if __name__ == '__main__':
    client = get_client()

    client.paises.delete_many({})
    client.departamentos.delete_many({})
    client.ciudades.delete_many({})
    client.atracciones.delete_many({})

    # def chunks(l, n):
    #     for i in range(0, len(l), n):
    #         yield l[i:i+n]

    # dynamodb = boto3.resource(
    #     'dynamodb',
    #     region_name='sa-east-1',
    #     aws_access_key_id=os.getenv('AWS_ACCESS_KEY'),
    #     aws_secret_access_key=os.getenv('AWS_SECRET_KEY'),
    # )
    paises_requests = []
    departamentos_requests = []
    ciudades_requests = []

    mydb = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci"
    )
    cursor = mydb.cursor(dictionary=True)

    cursor.execute(f"""
        SELECT idpais as id, nombre_pais as nombre, priority from paises
    """)

    paises = cursor.fetchall()

    for pais in paises:

        cursor.execute(f"""
            SELECT iddepartamento as id, nombre_departamento as nombre from departamentos WHERE paises_idpais = {pais['id']}
        """)

        departamentos = cursor.fetchall()

        ciudades_total = 0

        for departamento in departamentos:

            cursor.execute(f"""
                SELECT idciudad as id, nombre_ciudad as nombre from ciudades WHERE departamentos_iddepartamento = {departamento['id']}
            """)

            ciudades = cursor.fetchall()

            for ciudad in ciudades:
                ciudades_requests.append(InsertOne({
                    'ciudad_id': ciudad['id'],
                    'ciudad_nombre': ciudad['nombre'],
                    'departamento_id': departamento['id'],
                    'departamento_nombre': departamento['nombre'],
                    'pais_id': pais['id'],
                    'pais_nombre': pais['nombre'],
                    'scraped': False,
                    'priority': pais['priority'],
                    'dest_mid': None,
                    'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }))

            ciudades_total += len(ciudades)

            departamentos_requests.append(InsertOne({
                'departamento_id': departamento['id'],
                'departamento_nombre': departamento['nombre'],
                'pais_id': pais['id'],
                'pais_nombre': pais['nombre'],
                'ciudades_count': len(ciudades),
                'scraped': False,
                'priority': pais['priority'],
                'dest_mid': None,
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }))

        paises_requests.append(InsertOne({
            'pais_id': pais['id'],
            'pais_nombre': pais['nombre'],
            'departamentos_count': len(departamentos),
            'ciudades_count': ciudades_total,
            'scraped': False,
            'priority': pais['priority'],
            'dest_mid': None,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }))

    client.paises.bulk_write(paises_requests)
    client.departamentos.bulk_write(departamentos_requests)
    client.ciudades.bulk_write(ciudades_requests)

    print('Paises:', client.paises.count_documents({}))
    print('Departamentos:', client.departamentos.count_documents({}))
    print('Ciudades:', client.ciudades.count_documents({}))
    # # scan = dynamodb.Table('tripendar_paises').scan(
    # #     FilterExpression=Key('nombre').eq('España')
    # # )

    # # print(scan)
