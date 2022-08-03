import asyncpg


async def introduce_tables(pool: asyncpg.pool.Pool, table_collection: list[dict]) -> None:
    async with pool.acquire() as connection:
        for table in table_collection:
            name = table.get("name", None)
            fields = table.get("fields", None)
            other_params = table.get("other_params", None)

            if type(name) is not str or type(fields) is not list or type(other_params) is not list or len(
                    [field for field in fields + other_params if type(field) is not str]) > 0:
                continue

            a = f"""CREATE TABLE IF NOT EXISTS {name} (
                 {("," + chr(10) + " ").join(fields + other_params)}
                )
                """

            try:
                await connection.execute(a)
            except Exception:
                print(f"Something went wrong creating the table {name} with \n{a}")


async def insert_migrate_column_if_not_exists(pool: asyncpg.pool.Pool, table_name: str, column_name: str,
                                              column_params: str = None, rename_from: str = None,
                                              create_if_not_exists: bool = True) -> None:
    try:
        async with pool.acquire() as connection:
            available_columns = await connection.fetch(
                f"SELECT column_name FROM information_schema.columns WHERE table_name='{table_name}'")
            available_columns = [column["column_name"] for column in available_columns]

            if column_name not in available_columns:
                if type(rename_from) is str:
                    print(f"Renaming column {rename_from} to {column_name} in {table_name}")
                    await connection.execute(f"ALTER TABLE {table_name} RENAME COLUMN {rename_from} TO {column_name}")
                elif create_if_not_exists:
                    print(f"Adding {column_name} to {table_name}")
                    await connection.execute(f"ALTER TABLE {table_name} ADD {column_name} {column_params}")
    except Exception as e:
        print(f"{e}\nThe above occurred when trying to insert {column_name} into {table_name}")


async def insert_cog_db_columns_if_not_exists(pool: asyncpg.pool.Pool, table_collection: list[dict]) -> None:
    if type(table_collection) is not list:
        return

    async with pool.acquire() as connection:
        for table in table_collection:
            if type(table) is not dict:
                continue

            name = table.get("name", None)
            fields_params = table.get("fields", None)
            renames = table.get("migrate", {})

            if type(name) is not str or type(fields_params) is not list or len(
                    [field for field in fields_params if type(field) is not str]) > 0:
                continue

            field_names = []
            field_cond = []

            for field in fields_params:
                field_names.append(field[:field.index(" ")])
                field_cond.append(field[field.index(" ") + 1:])

            available_columns = await connection.fetch(
                f"SELECT column_name FROM information_schema.columns WHERE table_name='{name}'")
            available_columns = [column["column_name"] for column in available_columns]

            for field_name in field_names:  # idea of this is to add new columns added to cog configs automatically without needing to do it manually
                await insert_migrate_column_if_not_exists(pool, name, field_name,
                                                          column_params=field_cond[field_names.index(field_name)],
                                                          rename_from=renames.get(field_name, None))

            for rename in renames:  # this is technically undefined behaviour since ordinarily configs shouldn't be requesting renames for columns that aren't specified but we're making use of it for config ;)
                if rename not in field_names:  # ie already done above
                    await insert_migrate_column_if_not_exists(pool, name, rename, rename_from=renames.get(rename),
                                                              create_if_not_exists=False)  # won't know types + handled by config anyway to save db space

            if name != "config":
                [print(f"INFO: Phantom DB column {column} in {name}") for column in available_columns if
                 column not in field_names]  # don't delete in case they're still needed
