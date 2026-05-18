# apps/api/assets

Binarios estáticos del backend que se suben a R2 mediante scripts dedicados.

## webcafeina-email-logo.png

Logo del header de los correos de outreach (v0.14.0). Especificación:

- **Ancho objetivo**: ~600 px (renderizado a 160 px en el cliente, pero el
  doble para retina/4k).
- **Formato**: PNG con canal alpha (fondo transparente).
- **Variante**: oscura sobre fondo blanco (los clientes de email no respetan
  prefer-color-scheme de forma fiable).
- **Peso**: ideal < 30 KB para no engordar el correo.

Una vez colocado:

```bash
python scripts/upload_email_logo.py
```

El script lo sube a `branding/webcafeina-email-logo.png` en el bucket R2
configurado y printa la URL pública. Copia esa URL a `.env` como
`EMAIL_LOGO_URL=` y reinicia el worker.

Si el archivo no está presente al desplegar, el layout maestro cae a
`webcafeína` como texto estilado (definido en
`packages/db-schema/alembic/versions/0005_email_html_layout.py`).
