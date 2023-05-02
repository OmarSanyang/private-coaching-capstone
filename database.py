import pymysql.cursors

def get_connection():
    connection = pymysql.connect(
        host='localhost',
        user='root',
        password='Mariama8!',
        db='private_coaching',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    return connection





