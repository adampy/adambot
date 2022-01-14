async def introduce_tables(pool, table_collection: list[dict]) -> None:
    async with pool.acquire() as connection:
        for table in table_collection:
            name = table.get("name", None)
            fields = table.get("fields", None)
            other_params = table.get("other_params", None)

            if type(name) is not str or type(fields) is not list or type(other_params) is not list or len([field for field in fields + other_params if type(field) is not str]) > 0:
                continue

            a = f"""CREATE TABLE IF NOT EXISTS {name} (
                 {("," + chr(10) + " ").join(fields + other_params)}
                )
                """

            try:
                await connection.execute(a)
            except Exception:
                print(f"Something went wrong creating the table {name} with \n{a}")


async def insert_columns_if_not_exists(pool, table_collection: list[dict]):
    if type(table_collection) is not list:
        return

    async with pool.acquire() as connection:
        for table in table_collection:
            if type(table) is not dict:
                continue

            name = table.get("name", None)
            fields_params = table.get("fields", None)
            renames = table.get("migrate", None)

            if type(name) is not str or type(fields_params) is not list or len([field for field in fields_params if type(field) is not str]) > 0:
                continue

            field_names = []
            field_cond = []

            for field in fields_params:
                field_names.append(field[:field.index(" ")])
                field_cond.append(field[field.index(" ") + 1:])

            available_columns = await connection.fetch(f"SELECT column_name FROM information_schema.columns WHERE table_name='{name}'")
            available_columns = [column["column_name"] for column in available_columns]

            for field_name in field_names:  # idea of this is to add new columns added to cog configs automatically without needing to do it manually
                if field_name not in available_columns:
                    print(f"Checking for {field_name} rename")
                    rename = renames.get(field_name, None) if renames else None

                    if rename:
                        print(f"Renaming column {rename} to {field_name} in {name}")
                        await connection.execute(f"ALTER TABLE {name} RENAME COLUMN {rename} TO {field_name}")
                    else:
                        print(f"Adding column {field_name} to {name}")
                        await connection.execute(f"ALTER TABLE {name} ADD {field_name} {field_cond[field_names.index(field_name)]}")
            [print(f"INFO: Phantom DB column {column} in {name}") for column in available_columns if column not in field_names]  # don't delete in case they're still needed

