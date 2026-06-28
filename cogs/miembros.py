import discord
from discord.ext import commands
from discord import app_commands
from datetime import date, datetime
import os
import database


def dias_desde(fecha_str: str) -> int:
    if not fecha_str:
        return 0
    return (date.today() - datetime.strptime(fecha_str, "%Y-%m-%d").date()).days


class SemanaModal(discord.ui.Modal, title="Actualización Semanal"):
    ausentes = discord.ui.TextInput(
        label="Ausentes esta semana (uno por línea)",
        style=discord.TextStyle.paragraph,
        placeholder="Deja vacío si todos estuvieron activos\nNombre1\nNombre2",
        required=False,
        max_length=2000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        nombres_ausentes = (
            [n.strip() for n in self.ausentes.value.replace(",", "\n").split("\n") if n.strip()]
            if self.ausentes.value.strip()
            else []
        )

        actualizados, no_encontrados = await database.actualizar_semana(nombres_ausentes)

        msg = f"✅ **Semana actualizada.** {actualizados} miembro(s) marcado(s) como activos."
        if nombres_ausentes:
            encontrados = [n for n in nombres_ausentes if n not in no_encontrados]
            if encontrados:
                msg += f"\n⚠️ Ausentes registrados: {', '.join(encontrados)}"
        if no_encontrados:
            msg += f"\n❓ No encontrados en el clan: {', '.join(no_encontrados)}"

        await interaction.response.send_message(msg)


class ImportarModal(discord.ui.Modal, title="Importar Miembros"):
    lista = discord.ui.TextInput(
        label="Miembros (uno por línea o separados por coma)",
        style=discord.TextStyle.paragraph,
        placeholder="Nombre1\nNombre2\nNombre3",
        required=True,
        max_length=4000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        nombres = [
            n.strip()
            for n in self.lista.value.replace(",", "\n").split("\n")
            if n.strip()
        ]
        agregados, existentes = [], []
        for nombre in nombres:
            if await database.agregar_miembro(nombre):
                agregados.append(nombre)
            else:
                existentes.append(nombre)

        msg = f"✅ **{len(agregados)} miembro(s) importado(s).**"
        if existentes:
            msg += f"\n⚠️ Ya existían: {', '.join(existentes)}"
        await interaction.response.send_message(msg, ephemeral=True)


class Miembros(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    strike = app_commands.Group(name="strike", description="Gestión de strikes")
    config = app_commands.Group(name="config", description="Configuración del bot")

    def es_staff(self, interaction: discord.Interaction) -> bool:
        staff_role_id = os.getenv("STAFF_ROLE_ID")
        if staff_role_id:
            return any(r.id == int(staff_role_id) for r in interaction.user.roles)
        perms = interaction.user.guild_permissions
        return perms.administrator or perms.manage_guild

    async def sin_permiso(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "❌ No tienes permisos para usar este comando.", ephemeral=True
        )

    # ── Miembros ─────────────────────────────────────────────────────────────

    @app_commands.command(name="agregar", description="Agregar un nuevo miembro al clan")
    async def agregar(
        self,
        interaction: discord.Interaction,
        nombre: str,
        usuario: discord.Member = None,
    ):
        if not self.es_staff(interaction):
            return await self.sin_permiso(interaction)

        ok = await database.agregar_miembro(nombre, usuario.id if usuario else None)
        if ok:
            msg = f"✅ **{nombre}** agregado al clan."
            if usuario:
                msg += f" Vinculado a {usuario.mention}."
            await interaction.response.send_message(msg)
        else:
            await interaction.response.send_message(
                f"❌ Ya existe un miembro llamado **{nombre}**.", ephemeral=True
            )

    @app_commands.command(name="remover", description="Remover un miembro del clan")
    async def remover(self, interaction: discord.Interaction, nombre: str):
        if not self.es_staff(interaction):
            return await self.sin_permiso(interaction)

        ok = await database.remover_miembro(nombre)
        if ok:
            await interaction.response.send_message(f"✅ **{nombre}** removido del clan.")
        else:
            await interaction.response.send_message(
                f"❌ No se encontró ningún miembro activo llamado **{nombre}**.", ephemeral=True
            )

    @app_commands.command(name="perfil", description="Ver el perfil de un miembro")
    async def perfil(self, interaction: discord.Interaction, nombre: str):
        if not self.es_staff(interaction):
            return await self.sin_permiso(interaction)

        m = await database.get_miembro(nombre)
        if not m:
            await interaction.response.send_message(
                f"❌ No se encontró ningún miembro activo llamado **{nombre}**.", ephemeral=True
            )
            return

        max_strikes = int(await database.get_config("max_strikes"))
        dias_limite = int(await database.get_config("dias_inactividad"))
        dias = dias_desde(m["ultima_actividad"])

        if m["ausencia_justificada"]:
            estado, color = "🟡 Ausencia justificada", 0xF39C12
        elif dias >= dias_limite:
            estado, color = f"🔴 Inactivo ({dias} días)", 0xE74C3C
        else:
            estado, color = f"🟢 Activo ({dias} días)", 0x2ECC71

        embed = discord.Embed(title=f"📋 {m['nombre']}", color=color)
        embed.add_field(name="Estado", value=estado, inline=True)
        embed.add_field(
            name="Strikes",
            value=f"{'⚠️ ' if m['strikes'] >= max_strikes else ''}{m['strikes']}/{max_strikes}",
            inline=True,
        )
        embed.add_field(name="Ingreso", value=m["fecha_ingreso"] or "—", inline=True)
        embed.add_field(name="Última actividad", value=m["ultima_actividad"] or "—", inline=True)
        embed.add_field(
            name="Discord",
            value=f"<@{m['discord_id']}>" if m["discord_id"] else "No vinculado",
            inline=True,
        )
        if m["justificacion"]:
            embed.add_field(name="Justificación", value=m["justificacion"], inline=False)
        if m["notas"]:
            embed.add_field(name="Notas", value=m["notas"], inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="lista", description="Ver el estado de todos los miembros")
    async def lista(self, interaction: discord.Interaction):
        if not self.es_staff(interaction):
            return await self.sin_permiso(interaction)

        miembros = await database.get_todos_miembros()
        if not miembros:
            await interaction.response.send_message("No hay miembros registrados.", ephemeral=True)
            return

        max_strikes = int(await database.get_config("max_strikes"))
        dias_limite = int(await database.get_config("dias_inactividad"))

        activos, justificados, inactivos, con_strikes = [], [], [], []
        for m in miembros:
            dias = dias_desde(m["ultima_actividad"])
            if m["strikes"] >= max_strikes:
                con_strikes.append(f"**{m['nombre']}** ({m['strikes']} strikes)")
            elif m["ausencia_justificada"]:
                justificados.append(f"**{m['nombre']}**")
            elif dias >= dias_limite:
                inactivos.append(f"**{m['nombre']}** ({dias}d)")
            else:
                activos.append(m["nombre"])

        embed = discord.Embed(
            title=f"👥 Miembros del Clan ({len(miembros)})", color=0x3498DB
        )

        def campo(nombres: list, limite=30) -> str:
            if not nombres:
                return "—"
            if len(nombres) > limite:
                return ", ".join(nombres[:limite]) + f"... y {len(nombres) - limite} más"
            return ", ".join(nombres)

        embed.add_field(
            name=f"🟢 Activos ({len(activos)})", value=campo(activos), inline=False
        )
        if justificados:
            embed.add_field(
                name=f"🟡 Ausencia justificada ({len(justificados)})",
                value=campo(justificados),
                inline=False,
            )
        if inactivos:
            embed.add_field(
                name=f"🔴 Inactivos +{dias_limite}d ({len(inactivos)})",
                value=campo(inactivos),
                inline=False,
            )
        if con_strikes:
            embed.add_field(
                name=f"⚠️ Strikes máximos ({len(con_strikes)})",
                value="\n".join(con_strikes),
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="semana", description="Actualización semanal: marca activos a todos excepto los ausentes")
    async def semana(self, interaction: discord.Interaction):
        if not self.es_staff(interaction):
            return await self.sin_permiso(interaction)
        await interaction.response.send_modal(SemanaModal())

    @app_commands.command(name="importar", description="Importar lista de miembros del juego")
    async def importar(self, interaction: discord.Interaction):
        if not self.es_staff(interaction):
            return await self.sin_permiso(interaction)
        await interaction.response.send_modal(ImportarModal())

    @app_commands.command(name="vincular", description="Vincular un miembro a su cuenta de Discord")
    async def vincular(
        self, interaction: discord.Interaction, nombre: str, usuario: discord.Member
    ):
        if not self.es_staff(interaction):
            return await self.sin_permiso(interaction)

        ok = await database.vincular_discord(nombre, usuario.id)
        if ok:
            await interaction.response.send_message(
                f"✅ **{nombre}** vinculado a {usuario.mention}."
            )
        else:
            await interaction.response.send_message(
                f"❌ No se encontró ningún miembro activo llamado **{nombre}**.", ephemeral=True
            )

    @app_commands.command(name="activo", description="Marcar a un miembro como activo hoy")
    async def activo(self, interaction: discord.Interaction, nombre: str):
        if not self.es_staff(interaction):
            return await self.sin_permiso(interaction)

        ok = await database.actualizar_actividad(nombre)
        if ok:
            await interaction.response.send_message(
                f"✅ Actividad de **{nombre}** actualizada a hoy."
            )
        else:
            await interaction.response.send_message(
                f"❌ No se encontró ningún miembro activo llamado **{nombre}**.", ephemeral=True
            )

    @app_commands.command(name="ausente", description="Registrar ausencia de un miembro")
    async def ausente(
        self, interaction: discord.Interaction, nombre: str, justificacion: str = None
    ):
        if not self.es_staff(interaction):
            return await self.sin_permiso(interaction)

        ok = await database.marcar_ausencia(nombre, justificacion)
        if ok:
            msg = f"🟡 Ausencia de **{nombre}** registrada."
            if justificacion:
                msg += f"\nJustificación: _{justificacion}_"
            await interaction.response.send_message(msg)
        else:
            await interaction.response.send_message(
                f"❌ No se encontró ningún miembro activo llamado **{nombre}**.", ephemeral=True
            )

    @app_commands.command(name="notas", description="Agregar notas al perfil de un miembro")
    async def notas(self, interaction: discord.Interaction, nombre: str, texto: str):
        if not self.es_staff(interaction):
            return await self.sin_permiso(interaction)

        ok = await database.agregar_notas(nombre, texto)
        if ok:
            await interaction.response.send_message(f"✅ Notas actualizadas para **{nombre}**.")
        else:
            await interaction.response.send_message(
                f"❌ No se encontró ningún miembro activo llamado **{nombre}**.", ephemeral=True
            )

    # ── Strikes ───────────────────────────────────────────────────────────────

    @strike.command(name="agregar", description="Agregar un strike a un miembro")
    async def strike_agregar(
        self, interaction: discord.Interaction, nombre: str, motivo: str = None
    ):
        if not self.es_staff(interaction):
            return await self.sin_permiso(interaction)

        ok, strikes = await database.agregar_strike(nombre, motivo)
        if not ok:
            await interaction.response.send_message(
                f"❌ No se encontró ningún miembro activo llamado **{nombre}**.", ephemeral=True
            )
            return

        max_strikes = int(await database.get_config("max_strikes"))
        msg = f"⚠️ Strike agregado a **{nombre}**. Total: {strikes}/{max_strikes}."
        if motivo:
            msg += f"\nMotivo: _{motivo}_"
        if strikes >= max_strikes:
            msg += f"\n🔴 **¡{nombre} ha alcanzado el máximo de strikes!**"
        await interaction.response.send_message(msg)

    @strike.command(name="quitar", description="Quitar un strike a un miembro")
    async def strike_quitar(self, interaction: discord.Interaction, nombre: str):
        if not self.es_staff(interaction):
            return await self.sin_permiso(interaction)

        ok, strikes = await database.remover_strike(nombre)
        if ok:
            max_strikes = int(await database.get_config("max_strikes"))
            await interaction.response.send_message(
                f"✅ Strike removido de **{nombre}**. Total: {strikes}/{max_strikes}."
            )
        else:
            await interaction.response.send_message(
                f"❌ No se encontró ningún miembro activo llamado **{nombre}**.", ephemeral=True
            )

    # ── Config ────────────────────────────────────────────────────────────────

    @config.command(name="ver", description="Ver la configuración actual del bot")
    async def config_ver(self, interaction: discord.Interaction):
        if not self.es_staff(interaction):
            return await self.sin_permiso(interaction)

        dias = await database.get_config("dias_inactividad")
        strikes = await database.get_config("max_strikes")
        canal_id = os.getenv("ALERT_CHANNEL_ID", "No configurado")

        embed = discord.Embed(title="⚙️ Configuración", color=0x95A5A6)
        embed.add_field(name="Días de inactividad", value=dias, inline=True)
        embed.add_field(name="Strikes máximos", value=strikes, inline=True)
        embed.add_field(
            name="Canal de alertas",
            value=f"<#{canal_id}>" if canal_id.isdigit() else canal_id,
            inline=True,
        )
        await interaction.response.send_message(embed=embed)

    @config.command(name="dias", description="Configurar días de inactividad para alerta")
    async def config_dias(self, interaction: discord.Interaction, dias: int):
        if not self.es_staff(interaction):
            return await self.sin_permiso(interaction)
        if dias < 1:
            await interaction.response.send_message(
                "❌ El valor debe ser mayor a 0.", ephemeral=True
            )
            return
        await database.set_config("dias_inactividad", str(dias))
        await interaction.response.send_message(
            f"✅ Días de inactividad configurados a **{dias}**."
        )

    @config.command(name="strikes", description="Configurar el máximo de strikes permitidos")
    async def config_strikes(self, interaction: discord.Interaction, maximo: int):
        if not self.es_staff(interaction):
            return await self.sin_permiso(interaction)
        if maximo < 1:
            await interaction.response.send_message(
                "❌ El valor debe ser mayor a 0.", ephemeral=True
            )
            return
        await database.set_config("max_strikes", str(maximo))
        await interaction.response.send_message(
            f"✅ Máximo de strikes configurado a **{maximo}**."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Miembros(bot))
