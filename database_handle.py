import asyncpg

async def create_tables_if_not_exists(pool: asyncpg.pool.Pool):
    """Procedure that creates the tables necessary if they do not already exist"""
    async with pool.acquire() as connection:
        # Config table
        await connection.execute("""CREATE TABLE IF NOT EXISTS config(
            guild_id BIGINT PRIMARY KEY,
            welcome_channel BIGINT,
            welcome_msg VARCHAR(1023),
            support_log_channel BIGINT,
            staff_role BIGINT,
            qotd_role BIGINT,
            qotd_limit INT DEFAULT 0,
            qotd_channel BIGINT,
            muted_role BIGINT,
            mod_log_channel BIGINT,
            prefix VARCHAR(1023) DEFAULT '-',
            bruhs INT DEFAULT 0
        )""") # bruhs counts how many bruh moments a guild has had

        # Censor table
        await connection.execute("""CREATE TABLE IF NOT EXISTS censor(
            guild_id BIGINT PRIMARY KEY,
            censors TEXT
        
        )""")

        # QOTD table
        await connection.execute("""CREATE TABLE IF NOT EXISTS qotd(
            id SERIAL PRIMARY KEY,
            question VARCHAR(255) NOT NULL,
            submitted_by BIGINT NOT NULL,
            submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            guild_id BIGINT NOT NULL
        )""")

        # Todo table
        await connection.execute("""CREATE TABLE IF NOT EXISTS todo(
            id SERIAL PRIMARY KEY,
            todo_id INT,
            todo_time TIMESTAMPTZ,
            member_id BIGINT
        )""")

        # Support table
        await connection.execute("""CREATE TABLE IF NOT EXISTS support(
            id SERIAL PRIMARY KEY,
            member_id BIGINT,
            staff_id BIGINT,
            guild_id BIGINT,
            started_at TIMESTAMPTZ
        )""")

        # Remind table
        await connection.execute("""CREATE TABLE IF NOT EXISTS warn(
            id SERIAL PRIMARY KEY,
            member_id BIGINT,
            staff_id BIGINT,
            warned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            reason VARCHAR(255),
            channel_id BIGINT
        )""")

        # Warn table
        await connection.execute("""CREATE TABLE IF NOT EXISTS warn(
            id SERIAL PRIMARY KEY,
            member_id BIGINT,
            staff_id BIGINT,
            warned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            reason VARCHAR(255),
            guild_id BIGINT
        )""")

        # Rep table
        await connection.execute("""CREATE TABLE IF NOT EXISTS rep(
            member_id BIGINT,
            guild_id BIGINT,
            reps INT
        )""")

        # Demographic roles table
        await connection.execute("""CREATE TABLE IF NOT EXISTS demographic_roles(
            id SERIAL PRIMARY KEY,
            sample_rate int NOT NULL DEFAULT 1,
            guild_id bigint NOT NULL,
            role_id bigint NOT NULL
        )""")

        # Demographic samples table
        await connection.execute("""CREATE TABLE IF NOT EXISTS demographic_samples(
            n int NOT NULL DEFAULT 0,
            taken_at timestamptz NOT NULL DEFAULT now(),
            role_reference int NOT NULL,
            CONSTRAINT fk_role_reference 
                    FOREIGN KEY (role_reference)
                        REFERENCES demographic_roles(id)
                        ON DELETE CASCADE
        )""")