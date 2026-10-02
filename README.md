# Dashboard LeeA · CLI-1001

Portal Flask berasingan untuk Architech Systems (`architechsystems`), berdasarkan
reka bentuk `portal-template` CLI-1000. Versi ini **baca sahaja**: senarai
prospek dan 100 mesej terakhir bagi setiap prospek daripada PostgreSQL. Paparan
dikemas kini melalui WebSocket Railway, dengan polling 5 saat sebagai sandaran.
Query
sentiasa menapis `clients.username = 'architechsystems'` dan `messages.client_id`
yang sepadan. `CLI-1001` ialah rujukan perniagaan, bukan primary key PostgreSQL.

Tetapkan `DATABASE_URL` (rujukan Railway Postgres jika di Railway),
`PORTAL_PASSWORD` yang kuat, dan `SECRET_KEY` rawak yang panjang dalam variables
deployment. Jangan commit nilai sebenar. Portal dan bot perlu mengakses database
Postgres yang sama; jika portal di Vercel, alamat Postgres dalaman Railway tidak
boleh dicapai dari Vercel. Gunakan sambungan selamat yang sesuai atau hos portal
di rangkaian Railway. Aplikasi ini tidak memuatkan `.env` secara automatik.
Jika portal di Vercel dan bot di Railway, gunakan alamat Postgres awam yang
selamat untuk portal (bukan alamat `railway.internal`). Bot boleh menggunakan
alamat dalaman Railway. Kedua-duanya mesti menuju pangkalan data yang sama.
Data chat hanya boleh dibaca melalui API selepas login; portal kekal baca sahaja.
Tetapkan `CHAT_SOCKET_SECRET` rawak yang sama (sekurang-kurangnya 32 aksara) pada
bot Railway dan portal Vercel. Pada portal tetapkan `CHAT_SOCKET_URL` kepada
`wss://<domain-awam-bot-railway>/ws/chat`. Pada bot tetapkan `CHAT_SOCKET_ORIGIN`
kepada origin HTTPS portal Vercel yang tepat (tanpa `/` di akhir). Endpoint hanya
menerima tiket bertandatangan berumur maksimum 120 saat selepas login portal;
tiada data chat dihantar melalui WebSocket, hanya isyarat untuk refresh API.

Sebelum digunakan pelanggan: jalankan `schema.sql`/migrasi LeeA dengan selamat,
sahkan data dan SSL sambungan, uji login serta penapisan tenant pada deployment
sebenar. Bot masih mempunyai endpoint chat lama yang tidak disahkan; jangan
dedahkan endpoint tersebut sebagai fungsi portal. Balasan admin, mod human,
langganan dan tetapan belum disediakan; tiada butang untuk fungsi itu.

## Semakan sebelum diberikan kepada klien

Upload **kandungan folder ini sahaja** ke akar repo GitHub, bukan `.env`. Di
Vercel import repo dengan Root Directory `./` (jika fail `app.py` di akar repo),
tetapkan lima variable dalam `.env.example` untuk Production, kemudian Deploy.
Selepas dapat domain Vercel, tetapkan `CHAT_SOCKET_ORIGIN` pada bot Railway kepada
origin HTTPS portal itu (contoh `https://nama.vercel.app`, tanpa slash akhir).
Jika mengubah variable Vercel selepas deploy, redeploy supaya deployment aktif
menggunakan tetapan baharu.

Uji sebagai klien: tanpa login `/api/leads` mesti menolak akses; selepas login
senarai prospek dan sejarah mesej mesti muncul. Hantar mesej ujian WhatsApp
kepada bot LeeA dan sahkan mesej masuk **serta balasan bot** muncul; WebSocket
mempercepat refresh, polling setiap 5 saat ialah sandaran. Jika login gagal,
semak `PORTAL_PASSWORD`/`SECRET_KEY`; jika senarai gagal, semak URL PostgreSQL
awam, rangkaian/SSL serta jadual `clients`/`messages`; jika chat hanya refresh
setiap 5 saat, semak `CHAT_SOCKET_URL`, rahsia yang sama pada kedua-dua servis,
dan `CHAT_SOCKET_ORIGIN` pada Railway. Jangan kongsi URL atau log yang mengandungi
token/rahsia ketika menyemak masalah.

Portal ini **bukan sistem backup**. Sahkan backup PostgreSQL dijadualkan pada
penyedia database dan uji pemulihan ke database ujian secara berasingan;
jangan jalankan restore pada database produksi semata-mata untuk menguji portal.