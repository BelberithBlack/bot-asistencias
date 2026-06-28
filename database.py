import aiosqlite
from datetime import date, timedelta

DB_PATH = "asistencias.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS miembros (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre               TEXT UNIQUE NOT NULL COLLATE NOCASE,
                discord_id           INTEGER UNIQUE,
                strikes              INTEGER DEFAULT 0,
                ultima_actividad     TEXT,
                fecha_ingreso        TEXT DEFAULT (date('now')),
                ausencia_justificada INTEGER DEFAULT 0,
                justificacion        TEXT,
                notas                TEXT,
                activo               INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS historial (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                miembro_id  INTEGER NOT NULL,
                tipo        TEXT NOT NULL,
                fecha       TEXT DEFAULT (date('now')),
                detalle     TEXT,
                FOREIGN KEY (miembro_id) REFERENCES miembros(id)
            );
        """)
        await db.execute("INSERT OR IGNORE INTO config VALUES ('dias_inactividad', '30')")
        await db.execute("INSERT OR IGNORE INTO config VALUES ('max_strikes', '3')")
        await db.commit()


async def get_config(key: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM config WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def set_config(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO config VALUES (?, ?)", (key, value))
        await db.commit()


async def agregar_miembro(nombre: str, discord_id: int = None) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO miembros (nombre, discord_id, ultima_actividad) VALUES (?, ?, date('now'))",
                (nombre, discord_id),
            )
            await db.commit()
        return True
    except aiosqlite.IntegrityError:
        return False


async def remover_miembro(nombre: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "UPDATE miembros SET activo = 0 WHERE nombre = ? COLLATE NOCASE AND activo = 1",
            (nombre,),
        ) as cur:
            updated = cur.rowcount
        if updated:
            async with db.execute("SELECT id FROM miembros WHERE nombre = ? COLLATE NOCASE", (nombre,)) as c:
                row = await c.fetchone()
                if row:
                    await db.execute(
                        "INSERT INTO historial (miembro_id, tipo) VALUES (?, 'expulsion')", (row[0],)
                    )
        await db.commit()
        return updated > 0


async def get_miembro(nombre: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM miembros WHERE nombre = ? COLLATE NOCASE AND activo = 1", (nombre,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_todos_miembros() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM miembros WHERE activo = 1 ORDER BY nombre COLLATE NOCASE"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def actualizar_actividad(nombre: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """UPDATE miembros
               SET ultima_actividad = date('now'), ausencia_justificada = 0, justificacion = NULL
               WHERE nombre = ? COLLATE NOCASE AND activo = 1""",
            (nombre,),
        ) as cur:
            updated = cur.rowcount
        if updated:
            async with db.execute(
                "SELECT id FROM miembros WHERE nombre = ? COLLATE NOCASE", (nombre,)
            ) as c:
                row = await c.fetchone()
                if row:
                    await db.execute(
                        "INSERT INTO historial (miembro_id, tipo) VALUES (?, 'actividad')", (row[0],)
                    )
        await db.commit()
        return updated > 0


async def marcar_ausencia(nombre: str, justificacion: str = None) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """UPDATE miembros
               SET ausencia_justificada = 1, justificacion = ?
               WHERE nombre = ? COLLATE NOCASE AND activo = 1""",
            (justificacion, nombre),
        ) as cur:
            updated = cur.rowcount
        if updated:
            async with db.execute(
                "SELECT id FROM miembros WHERE nombre = ? COLLATE NOCASE", (nombre,)
            ) as c:
                row = await c.fetchone()
                if row:
                    await db.execute(
                        "INSERT INTO historial (miembro_id, tipo, detalle) VALUES (?, 'ausencia', ?)",
                        (row[0], justificacion),
                    )
        await db.commit()
        return updated > 0


async def agregar_strike(nombre: str, motivo: str = None) -> tuple[bool, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "UPDATE miembros SET strikes = strikes + 1 WHERE nombre = ? COLLATE NOCASE AND activo = 1",
            (nombre,),
        ) as cur:
            if not cur.rowcount:
                return False, 0
        async with db.execute(
            "SELECT id, strikes FROM miembros WHERE nombre = ? COLLATE NOCASE", (nombre,)
        ) as c:
            row = await c.fetchone()
            miembro_id, strikes = row
        await db.execute(
            "INSERT INTO historial (miembro_id, tipo, detalle) VALUES (?, 'strike', ?)",
            (miembro_id, motivo),
        )
        await db.commit()
        return True, strikes


async def remover_strike(nombre: str) -> tuple[bool, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "UPDATE miembros SET strikes = MAX(0, strikes - 1) WHERE nombre = ? COLLATE NOCASE AND activo = 1",
            (nombre,),
        ) as cur:
            if not cur.rowcount:
                return False, 0
        async with db.execute(
            "SELECT id, strikes FROM miembros WHERE nombre = ? COLLATE NOCASE", (nombre,)
        ) as c:
            row = await c.fetchone()
            miembro_id, strikes = row
        await db.execute(
            "INSERT INTO historial (miembro_id, tipo) VALUES (?, 'strike_removido')", (miembro_id,)
        )
        await db.commit()
        return True, strikes


async def vincular_discord(nombre: str, discord_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "UPDATE miembros SET discord_id = ? WHERE nombre = ? COLLATE NOCASE AND activo = 1",
            (discord_id, nombre),
        ) as cur:
            updated = cur.rowcount
        await db.commit()
        return updated > 0


async def agregar_notas(nombre: str, texto: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "UPDATE miembros SET notas = ? WHERE nombre = ? COLLATE NOCASE AND activo = 1",
            (texto, nombre),
        ) as cur:
            updated = cur.rowcount
        await db.commit()
        return updated > 0


async def actualizar_semana(nombres_ausentes: list[str]) -> tuple[int, list[str]]:
    """Marca como activos todos los miembros excepto los ausentes.
    Devuelve (cantidad actualizados, nombres no encontrados en la lista de ausentes)."""
    ausentes_lower = {n.lower() for n in nombres_ausentes}
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, nombre FROM miembros WHERE activo = 1"
        ) as cur:
            todos = await cur.fetchall()

        no_encontrados = [n for n in nombres_ausentes if not any(n.lower() == m[1].lower() for m in todos)]
        actualizados = 0
        for miembro_id, nombre in todos:
            if nombre.lower() not in ausentes_lower:
                await db.execute(
                    """UPDATE miembros
                       SET ultima_actividad = date('now'), ausencia_justificada = 0, justificacion = NULL
                       WHERE id = ?""",
                    (miembro_id,),
                )
                await db.execute(
                    "INSERT INTO historial (miembro_id, tipo, detalle) VALUES (?, 'actividad', 'actualizacion semanal')",
                    (miembro_id,),
                )
                actualizados += 1
        await db.commit()
        return actualizados, no_encontrados


async def get_miembros_inactivos(dias: int) -> list[dict]:
    limite = (date.today() - timedelta(days=dias)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM miembros
               WHERE activo = 1
               AND ausencia_justificada = 0
               AND (ultima_actividad IS NULL OR ultima_actividad <= ?)
               ORDER BY ultima_actividad""",
            (limite,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_miembros_con_max_strikes(max_strikes: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM miembros WHERE activo = 1 AND strikes >= ? ORDER BY strikes DESC",
            (max_strikes,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]
