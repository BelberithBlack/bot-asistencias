# Bot de Asistencias — Clan Where Winds Meet

Bot de Discord para gestionar la asistencia y el estado de los miembros del clan.

## Requisitos

- Python 3.10+
- Las dependencias del archivo `requirements.txt`

```bash
pip install -r requirements.txt
```

## Configuración

1. Copia `.env.example` a `.env` y completa los valores:

```env
DISCORD_TOKEN=token_del_bot
ALERT_CHANNEL_ID=id_del_canal_de_alertas
STAFF_ROLE_ID=id_del_rol_de_staff  # opcional
```

2. Crea el bot en [discord.com/developers/applications](https://discord.com/developers/applications) y activa el **Server Members Intent**.

3. Invita el bot al servidor con los scopes `bot` y `applications.commands`, y permisos de Send Messages, Embed Links, Read Message History y Mention Everyone.

## Uso

```bash
python bot.py
```

## Comandos

### Gestión de miembros
| Comando | Descripción |
|---|---|
| `/agregar <nombre> [@discord]` | Agregar un miembro al clan |
| `/remover <nombre>` | Remover un miembro del clan |
| `/perfil <nombre>` | Ver el perfil completo de un miembro |
| `/lista` | Ver todos los miembros con su estado actual |
| `/importar` | Importar lista de miembros desde el juego |
| `/vincular <nombre> @discord` | Vincular un miembro a su cuenta de Discord |
| `/notas <nombre> <texto>` | Agregar notas al perfil de un miembro |

### Asistencia
| Comando | Descripción |
|---|---|
| `/semana` | Actualización semanal: marca activos a todos excepto los ausentes indicados |
| `/activo <nombre>` | Marcar a un miembro como activo puntualmente |
| `/ausente <nombre> [justificación]` | Registrar ausencia (con justificación evita la alerta de 30 días) |

### Strikes
| Comando | Descripción |
|---|---|
| `/strike agregar <nombre> [motivo]` | Agregar un strike |
| `/strike quitar <nombre>` | Quitar un strike |

### Alertas y configuración
| Comando | Descripción |
|---|---|
| `/revision` | Revisar manualmente miembros inactivos y con strikes máximos |
| `/config ver` | Ver la configuración actual |
| `/config dias <número>` | Configurar días de inactividad para alerta (default: 30) |
| `/config strikes <número>` | Configurar máximo de strikes (default: 3) |

## Flujo semanal recomendado

1. Revisar el clan en el juego
2. Correr `/semana` y anotar en el modal los miembros que **no** jugaron esa semana
3. Para ausencias justificadas, usar `/ausente <nombre> <justificación>` después
4. El bot envía alertas automáticas diarias al canal configurado si hay miembros con +30 días de inactividad o strikes máximos
