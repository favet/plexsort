# Finding Plex Settings for `.env`

PlexSort needs three Plex values in `.env`:

```dotenv
PLEX_URL=http://192.168.1.x:32400
PLEX_TOKEN=your-token-here
PLEX_LIBRARY=Movies
```

## `PLEX_URL`

This is the base URL for the Plex Media Server on your local network.

Usually it is:

```text
http://<local-server-ip>:32400
```

Plex's `plex.direct` HTTPS form is also valid:

```text
https://192-168-0-146.<server-id>.plex.direct:32400
```

Examples:

```text
http://192.168.1.25:32400
http://10.0.0.42:32400
http://localhost:32400
```

Use `localhost` only if Plex Media Server runs on the same machine as PlexSort.
Otherwise, use the local IP address of the machine running Plex Media Server.
Using a Plex `plex.direct` URL is fine when copied from Plex Web or server settings.

Plex's LAN/internal server port is normally `32400`.

Official reference:

- https://support.plex.tv/articles/200931138-troubleshooting-remote-access/

## `PLEX_TOKEN`

This is the `X-Plex-Token` value for your Plex account/server access.

Official Plex method:

1. Sign in to Plex Web App.
2. Open any movie in the target Plex library.
3. Use the item menu to view XML.
4. Look at the browser URL for `X-Plex-Token=...`.
5. Copy only the token value after `X-Plex-Token=`.

Keep this value private. It grants access to Plex API data.

Official reference:

- https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/

## `PLEX_LIBRARY`

This is the library name inside Plex, not a Windows folder path.

Examples:

```text
Movies
Films
4K Movies
Justin Movies
```

If your Plex sidebar has a movie library named `Movies`, then:

```dotenv
PLEX_LIBRARY=Movies
```

This is the Plex library section title. PlexSort uses it to ask Plex which library
section key to sync. It should not be `D:\Movies`, `C:\Media`, a network share, or
any other file directory.

Official reference:

- https://support.plex.tv/articles/200288926-creating-libraries/

## Quick Verification

After `.env` is filled in and the app dependencies are installed, the first real
verification checkpoint is:

1. Start Docker services.
2. Apply Alembic migrations.
3. Call `/health`.
4. Trigger Plex sync from the admin API.
5. Check `/api/movies` for safe movie rows.

Do not expose the site publicly until `/api/admin*` is confirmed protected by Caddy.
