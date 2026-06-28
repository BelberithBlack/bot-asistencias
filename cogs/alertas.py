import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import database


class Alertas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.revision_diaria.start()

    def cog_unload(self):
        self.revision_diaria.cancel()

    def get_canal(self) -> discord.TextChannel | None:
        canal_id = os.getenv("ALERT_CHANNEL_ID")
        if canal_id:
            return self.bot.get_channel(int(canal_id))
        return None

    def get_mencion(self) -> str:
        staff_role_id = os.getenv("STAFF_ROLE_ID")
        return f"<@&{staff_role_id}>" if staff_role_id else ""

    async def construir_reporte(self) -> discord.Embed | None:
        dias = int(await database.get_config("dias_inactividad"))
        max_strikes = int(await database.get_config("max_strikes"))

        inactivos = await database.get_miembros_inactivos(dias)
        con_strikes = await database.get_miembros_con_max_strikes(max_strikes)

        if not inactivos and not con_strikes:
            return None

        embed = discord.Embed(
            title="⚠️ Revisión del Clan",
            description="Los siguientes miembros requieren atención:",
            color=0xE74C3C,
        )

        if inactivos:
            lineas = [
                f"• **{m['nombre']}** — sin actividad desde `{m['ultima_actividad'] or 'sin registro'}`"
                for m in inactivos
            ]
            embed.add_field(
                name=f"🔴 Inactivos +{dias} días ({len(inactivos)})",
                value="\n".join(lineas),
                inline=False,
            )

        if con_strikes:
            lineas = [
                f"• **{m['nombre']}** — {m['strikes']} strikes"
                for m in con_strikes
            ]
            embed.add_field(
                name=f"⚠️ Strikes máximos ({len(con_strikes)})",
                value="\n".join(lineas),
                inline=False,
            )

        return embed

    @tasks.loop(hours=24)
    async def revision_diaria(self):
        canal = self.get_canal()
        if not canal:
            return
        embed = await self.construir_reporte()
        if embed:
            await canal.send(content=self.get_mencion(), embed=embed)

    @revision_diaria.before_loop
    async def before_revision(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="revision", description="Revisar manualmente el estado del clan")
    async def revision(self, interaction: discord.Interaction):
        staff_role_id = os.getenv("STAFF_ROLE_ID")
        if staff_role_id:
            autorizado = any(r.id == int(staff_role_id) for r in interaction.user.roles)
        else:
            perms = interaction.user.guild_permissions
            autorizado = perms.administrator or perms.manage_guild

        if not autorizado:
            await interaction.response.send_message(
                "❌ No tienes permisos para usar este comando.", ephemeral=True
            )
            return

        await interaction.response.defer()

        embed = await self.construir_reporte()
        canal = self.get_canal()

        if not embed:
            await interaction.followup.send(
                "✅ Todo en orden. No hay miembros que requieran atención. 🎉"
            )
            return

        if canal and canal != interaction.channel:
            await canal.send(content=self.get_mencion(), embed=embed)
            await interaction.followup.send(
                f"✅ Reporte enviado a {canal.mention}."
            )
        else:
            await interaction.followup.send(
                content=self.get_mencion(), embed=embed
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Alertas(bot))
