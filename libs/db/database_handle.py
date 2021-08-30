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
            bruhs INT DEFAULT 0,
            rep_award_banned BIGINT,
            rep_receive_banned BIGINT,
            jail_role BIGINT,
            trivia_channel BIGINT,
            invite_log_channel BIGINT
        )""") # bruhs counts how many bruh moments a guild has had

        # Filter table
        await connection.execute("""CREATE TABLE IF NOT EXISTS filter(
            guild_id BIGINT PRIMARY KEY,
            filters TEXT
        )""")

        # QOTD table
        await connection.execute("""CREATE TABLE IF NOT EXISTS qotd(
            id SERIAL PRIMARY KEY,
            question VARCHAR(255) NOT NULL,
            submitted_by BIGINT NOT NULL,
            submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            guild_id BIGINT NOT NULL
        )""")

        # Tasks table
        await connection.execute("""CREATE TABLE IF NOT EXISTS tasks(
            id SERIAL PRIMARY KEY,
            task_name VARCHAR(255) NOT NULL,
            task_time TIMESTAMPTZ,
            member_id BIGINT,
            guild_id BIGINT
        )""")

        # Support table
        await connection.execute("""CREATE TABLE IF NOT EXISTS support(
            id SERIAL PRIMARY KEY,
            member_id BIGINT,
            staff_id BIGINT,
            guild_id BIGINT,
            started_at TIMESTAMPTZ
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

        # Remind table
        await connection.execute("""CREATE TABLE IF NOT EXISTS remind(
            id SERIAL PRIMARY KEY,
            member_id BIGINT,
            reminder_time TIMESTAMPTZ,
            reminder VARCHAR(255),
            created_at TIMESTAMPTZ,
            channel_id BIGINT
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

        # Reaction role emoji table
        await connection.execute("""CREATE TABLE IF NOT EXISTS reaction_roles(
            message_id BIGINT NOT NULL,
            role_id BIGINT NOT NULL,
            guild_id BIGINT NOT NULL,
            channel_id BIGINT NOT NULL,
            inverse BOOLEAN DEFAULT FALSE,
            emoji TEXT,
            emoji_id BIGINT
        )""") # TODO: Normalise this table to 3NF?

        # Starboard table
        await connection.execute("""CREATE TABLE IF NOT EXISTS starboard(
            channel_id BIGINT PRIMARY KEY,
            guild_id BIGINT NOT NULL,
            emoji TEXT,
            emoji_id BIGINT,
            minimum_stars INT NOT NULL,
            embed_colour VARCHAR(7),
            allow_self_star BOOL
        )""")

        # Starboard entry table
        await connection.execute("""CREATE TABLE IF NOT EXISTS starboard_entry(
            message_id BIGINT NOT NULL,
            starboard_channel_id BIGINT NOT NULL,
            bot_message_id BIGINT NOT NULL,
            CONSTRAINT fk_starboard_reference 
                    FOREIGN KEY (starboard_channel_id)
                        REFERENCES starboard(channel_id)
                        ON DELETE CASCADE
        )""")
