# AppRole Artifacts

Este directorio queda vacío en el repositorio. Durante la ejecución de
`vault-setup`, Vault escribe aquí los archivos `role_id` y `secret_id` que el
Vault Agent usa para autenticarse mediante AppRole.

Los valores generados son efímeros y **no** deben versionarse. Los nombres de
archivo están listados en `.gitignore` para evitar que se agreguen accidentalmente.
