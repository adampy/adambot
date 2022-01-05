async def introduce_tables(pool, table_collection) -> None:
    async with pool.acquire() as connection:
        for table in table_collection:
            name = table.get("name", None)
            fields = table.get("fields", None)

            if type(name) is not str or type(fields) is not list or len([field for field in fields if type(field) is not str]) > 0:
                continue

            a = f"""CREATE TABLE IF NOT EXISTS {name} (
                 {("," + chr(10) + " ").join(fields)}
                )
                """

            try:
                await connection.execute(a)
            except Exception:
                print(f"Something went wrong creating the table {name} with \n{a}")
