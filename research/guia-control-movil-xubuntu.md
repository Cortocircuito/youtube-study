# Control de agentes desde el móvil — Xubuntu 24.04

Esta guía documenta la configuración elegida para controlar sesiones de terminal y agentes de IA desde el teléfono:

```text
Móvil: Tailscale + Moshi
             │
     red privada cifrada
             │
Xubuntu: Tailscale + OpenSSH + Mosh + tmux + agentes
```

No requiere abrir puertos en el router ni exponer servicios a Internet.

> Esta instalación usa **OpenSSH sobre la red de Tailscale**. Por compatibilidad con Moshi/Easy Pair se deja **Tailscale SSH desactivado**. No son dos capas de SSH que deban estar activas a la vez.

## Componentes

- **Tailscale:** crea la red privada entre el móvil y el Xubuntu.
- **OpenSSH (`sshd`):** acepta la conexión remota usando claves SSH.
- **Mosh:** transporte de terminal resistente a cambios entre Wi-Fi y datos móviles.
- **tmux:** mantiene agentes y terminales vivos aunque se desconecte el móvil.
- **Moshi:** aplicación móvil SSH/Mosh y sus herramientas auxiliares (`moshi-hook`).

## 1. Instalar OpenSSH, tmux, Mosh y firewall

En Xubuntu:

```bash
sudo apt update
sudo apt install -y openssh-server tmux mosh ufw
sudo systemctl enable --now ssh
```

Comprobar que el servidor SSH está activo:

```bash
systemctl status ssh --no-pager
```

## 2. Instalar y conectar Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Instala Tailscale también en el móvil e inicia sesión en la misma tailnet.

Comprobaciones útiles:

```bash
tailscale status
tailscale ip -4
```

## 3. Elegir OpenSSH, no Tailscale SSH

Tailscale SSH es un servidor SSH gestionado por Tailscale que intercepta el puerto 22 de las conexiones provenientes de la tailnet. Moshi Easy Pair instala una clave en `~/.ssh/authorized_keys` y necesita llegar al servidor OpenSSH normal.

Por eso se desactiva Tailscale SSH:

```bash
sudo tailscale set --ssh=false
```

Así, Tailscale cifra y enruta el tráfico, mientras que `sshd` autentica la clave del teléfono.

## 4. Firewall restringido a la tailnet

Antes de activar UFW, revisa las reglas existentes:

```bash
sudo ufw status numbered
```

Permite SSH y el rango UDP de Mosh únicamente por la interfaz virtual de Tailscale:

```bash
sudo ufw allow in on tailscale0 to any port 22 proto tcp
sudo ufw allow in on tailscale0 to any port 60000:61000 proto udp
sudo ufw enable
sudo ufw status verbose
```

Significado de la segunda regla:

- `in on tailscale0`: acepta solo tráfico que llega desde Tailscale.
- `60000:61000`: rango UDP que utiliza `mosh-server`.
- No abre ese rango al Internet público ni a la red local normal.

Si se usará exclusivamente SSH y no Mosh, se puede omitir la instalación de `mosh` y la regla UDP.

## 5. Instalar herramientas auxiliares de Moshi

```bash
curl -fsSL https://getmoshi.app/install.sh | sh
```

El script instala en `~/.local/bin`:

- `moshi-hook`: emparejamiento, hooks y notificaciones de agentes.
- `moshi`: atajo para crear o recuperar sesiones tmux.

No instala la app Moshi en el teléfono: se instala desde Google Play o App Store.

Durante la primera ejecución se eligieron estos valores:

```text
always-on-discovery: on
usage-collection: on
suppress-nested-agent-push: off
```

- **always-on-discovery:** sigue detectando servidores de desarrollo y simuladores locales.
- **usage-collection:** sincroniza el estado de límites de uso de agentes.
- **suppress-nested-agent-push: off:** conserva notificaciones y aprobaciones de subagentes.

La configuración se guarda en:

```text
~/.config/moshi/config.toml
```

## 6. Emparejar el móvil con Easy Pair

En Xubuntu ejecuta:

```bash
moshi-hook host setup
```

Aparecerá un código QR. En el móvil:

1. Abre Moshi.
2. Elige **Easy Pair**.
3. Escanea el QR.
4. Conecta al host creado; usa el modo de conexión **Auto**.

Moshi genera la clave privada en el teléfono y añade únicamente su clave pública a `~/.ssh/authorized_keys` en Xubuntu.

> El QR es un token temporal de acceso. No lo compartas.

## 7. Ejecutar agentes dentro de tmux

En Xubuntu, desde una terminal local o Moshi:

```bash
cd ~/Code/mi-proyecto
moshi .
```

`moshi .` crea o recupera una sesión tmux para ese directorio. Dentro, inicia el agente:

```bash
codex
# o: claude, pi, opencode, etc.
```

Para desconectarte sin detener el agente:

```text
Ctrl+B, D
```

Para reconectar posteriormente:

```bash
moshi ~/Code/mi-proyecto
```

Comandos tmux útiles:

```bash
tmux ls                         # lista sesiones
tmux attach -t NOMBRE_SESION    # recupera una sesión
tmux new -s agentes             # crea una sesión con nombre
```

## 8. Hooks y notificaciones de agentes (opcional)

Después de validar la conexión básica, en Moshi abre **Settings → Hooks** y copia el token. En Xubuntu:

```bash
moshi-hook pair --token "PEGA_AQUI_EL_TOKEN"
moshi-hook install
```

Para que el daemon se ejecute tras reinicios y cierres de sesión:

```bash
moshi-hook service install
moshi-hook service status
```

`moshi-hook serve` se usa solo para probarlo manualmente en primer plano; no es el modo recomendado para uso permanente en Xubuntu.

## Verificación final

Con el móvil usando datos móviles:

1. Activa Tailscale.
2. Abre Moshi y conecta al Xubuntu.
3. Ejecuta:

```bash
tmux ls
```

4. Recupera la sesión del proyecto:

```bash
moshi ~/Code/mi-proyecto
```

Si la conexión funciona, los agentes continuarán trabajando dentro de tmux aunque cierres Moshi. El Xubuntu debe permanecer encendido, conectado a Internet y dentro de la tailnet.

# Alternativa 1: Tailscale + Herdr

Herdr es un entorno de terminal persistente y orientado a agentes. Puede crear paneles, ejecutar varios agentes y distinguir estados como `working`, `idle`, `done` y `blocked`.

```text
Cliente de terminal por SSH ── Tailscale ── Xubuntu: Herdr + agentes
```

Esta alternativa no proporciona por sí sola una interfaz móvil específica: se accede a Herdr con un cliente de terminal, como Moshi. Tailscale aporta conectividad privada; Herdr organiza y supervisa los agentes.

## Instalación

Instala Herdr en Xubuntu:

```bash
curl -fsSL https://herdr.dev/install.sh | sh
```

Abre una terminal nueva y verifica:

```bash
herdr --version
```

Inicia la interfaz:

```bash
herdr
```

Instala y autentica en el propio Xubuntu los CLIs de los agentes que usarás, por ejemplo Codex, Claude Code o Pi. Las credenciales de otro equipo no se comparten automáticamente.

Herdr puede reconocer agentes lanzados desde sus paneles y permite controlarlos por nombre o panel. Ejemplo conceptual de lanzamiento desde un panel existente:

```bash
herdr agent start revisor --kind codex --pane w1:p2 -- -m gpt-5.4
```

Los IDs de panel (`w1:p2`) los devuelve Herdr al crear o dividir paneles; no deben inventarse.

## Ventajas y límites

- Más información sobre el estado de los agentes que tmux solo.
- Puede manejar múltiples agentes y paneles de forma estructurada.
- No requiere exponer puertos públicos: Tailscale sigue siendo suficiente.
- Desde Moshi continúa siendo una interfaz de terminal; no ofrece por sí mismo una experiencia móvil de tipo chat.

# Alternativa 2: Tailscale + Herdr + herdr-web

`herdr-web` es un plugin que abre el TUI real de Herdr en una web/PWA. Permite usarlo desde el navegador móvil y muestra paneles, pestañas, teclas rápidas y estados de los agentes.

```text
Móvil: navegador/PWA
          │ HTTPS privado de Tailscale
Xubuntu: Tailscale Serve → herdr-web → Herdr → agentes
```

No requiere OpenSSH, Tailscale SSH ni Moshi para el acceso diario a Herdr.

## Instalación

Primero instala Herdr siguiendo la sección anterior. Después instala el plugin:

```bash
herdr plugin install barnuri/herdr-web
```

El plugin sirve la interfaz en local, por defecto:

```text
http://127.0.0.1:7936
```

Inicia Herdr si no está en ejecución:

```bash
herdr
```

## Publicar únicamente dentro de Tailscale

Publica el servicio local como HTTPS privado de la tailnet:

```bash
tailscale serve --bg http://127.0.0.1:7936
tailscale serve status
```

Abre desde el móvil la URL HTTPS que muestre `tailscale serve status` e instálala como PWA si el navegador ofrece esa opción.

> `herdr-web` no incluye autenticación propia. Debe mantener su bind en `127.0.0.1` y exponerse solo mediante Tailscale Serve y ACLs/grants restrictivos de Tailscale. Nunca uses Tailscale Funnel para este servicio.

## Ventajas y límites

- No necesita SSH, claves ni una aplicación móvil de terminal.
- Es compatible con teléfonos que tengan un navegador moderno.
- Añade teclas rápidas táctiles y notificaciones web para agentes terminados o bloqueados.
- Consume algo más que Herdr solo: ejecuta un servidor web/Node, WebSocket y un terminal virtual por pestaña web.
- La interfaz sigue siendo un TUI dentro del navegador; Orca suele ofrecer una experiencia móvil más pulida para chat, aprobaciones, worktrees y Git.

## Desactivar herdr-web

Para retirar la publicación privada:

```bash
tailscale serve --bg off
```

Para consultar la configuración activa:

```bash
tailscale serve status
```
