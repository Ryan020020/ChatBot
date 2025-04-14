import mysql.connector

def insert_product_data(product_id, product_name, category, price, product_url):
    try:
        # DB 연결
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='1234',
            database='discord_bot'
        )
        cursor = connection.cursor()

        # Insert SQL
        sql = """
        INSERT INTO products (product_id, product_name, category, price, product_url)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
        product_name = VALUES(product_name), 
        category = VALUES(category),
        price = VALUES(price),
        product_url = VALUES(product_url);
        """
        values = (product_id, product_name, category, price, product_url)
        cursor.execute(sql, values)
        connection.commit()

    except mysql.connector.Error as err:
        print(f'Error: {err}')

    finally:
        cursor.close()
        connection.close()
