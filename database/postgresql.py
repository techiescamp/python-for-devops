import psycopg2

try:
    connection = psycopg2.connect(database="dvdrental",
                        host="192.168.5.5",
                        user="postgres",
                        password="myPassword",
                        port="5432")
    cursor = connection.cursor()
    sql_query = "select * from actor"

    cursor.execute(sql_query)
    print("Selecting rows from mobile table using cursor.fetchall")
    actor_records = cursor.fetchall()

    print("Print each row and it's columns values")
    for row in actor_records:
        print("Id = ", row[0], )
        print("Model = ", row[1])
        print("Price  = ", row[2], "\n")

except (Exception, psycopg2.Error) as error:
    print("Error while fetching data from PostgreSQL", error)

finally:
    if connection:
        cursor.close()
        connection.close()
        print("PostgreSQL connection is closed")
