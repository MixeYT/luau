# Mixe Launcher: analiza i projekt

## 1. Analiza popularnych launcherów

| Launcher | Technologia | Kod | Mody | Optymalizacja | Modpacki | Zarabianie |
|---|---|---|---|---|---|---|
| **Lunar Client** | Launcher w Electronie, własny zamknięty klient | zamknięty | własne wbudowane mody (HUD, keystrokes, zoom, FPS boost), na nowych wersjach część modów Fabric | własne poprawki silnika, wzorowane na Sodium | brak | kosmetyki, Lunar+ |
| **Feather Client** | Electron, klient oparty na Fabric | zamknięty | wbudowane mody + dodawanie modów z listy | wbudowane mody wydajnościowe | profile | kosmetyki, serwery Feather |
| **Badlion Client** | Electron, zamknięty klient | zamknięty | mody PvP (głównie 1.8.9) | własne | brak | kosmetyki |
| **Modrinth App** | Tauri (Rust + webowy UI) | otwarty | Modrinth | to, co sam zainstalujesz | .mrpack | reklamy w panelu |
| **Prism Launcher** | C++ / Qt (fork MultiMC) | otwarty | Modrinth, CurseForge | to, co sam zainstalujesz | .mrpack, CurseForge | brak |
| **CurseForge App** | Overwolf | zamknięty | CurseForge | brak | własny format | reklamy |

### Wnioski

- **Lunar, Feather i Badlion** wyglądają jak „własny klient”. Na nowych wersjach to w praktyce Fabric z paczką modów wydajnościowych i HUD-owych plus sklep z kosmetykami. Kosmetyki wymagają własnego serwera i backendu, więc nie są celem pierwszej wersji.
- **Modrinth App i Prism** pokazują, jak powinien działać dobry launcher:
  - osobne instancje,
  - pobieranie Javy,
  - mody z zależnościami,
  - standard modpacków `.mrpack`.
- **Optymalizacja** w nowym Minecrafcie to dziś zestaw modów z rodziny Sodium. Daje to samo, co „FPS boost” w zamkniętych klientach, a jest otwarte i aktualizowane.
- **Logowanie** wszędzie działa tak samo: konto Microsoft → Xbox Live → XSTS → token Minecraft.

Mixe Launcher bierze więc to, co najlepsze z obu grup. Wygląda i działa prosto jak Lunar czy Feather (jeden duży przycisk GRAJ, pakiet optymalizacyjny jednym kliknięciem). Pod spodem jest otwarty i przejrzysty jak Prism i Modrinth App: wiesz, jaki mod jest zainstalowany, skąd przyszedł i co robi.

## 2. Funkcje wersji 0.1

- **Konto:** logowanie Microsoft kodem urządzenia (wpisujesz kod na microsoft.com/link). Bez wbudowanej przeglądarki i bez lokalnego serwera.
- **Kilka kont:** przełączanie między kontami. Tokeny są szyfrowane przez `safeStorage` (na Windowsie to DPAPI).
- **Instancje:** każda ma własne `mods`, `config` i `saves`.
- **Wersje i loadery:** wszystkie wydania Minecrafta, Vanilla albo Fabric (najnowszy stabilny loader).
- **Pobieranie gry:** wersja, biblioteki, natywne biblioteki LWJGL, assety i config logów, każdy plik sprawdzany po SHA-1.
- **Java:** pobierana automatycznie, ta sama co w oficjalnym launcherze (Java 8, 17 lub 21, zależnie od wersji gry).
- **Mody:** wyszukiwarka Modrinth, instalacja z wymaganymi zależnościami, włączanie, wyłączanie i usuwanie.
- **Pakiet optymalizacyjny:** jednym przyciskiem albo od razu przy tworzeniu instancji.
- **Modpacki:** eksport instancji do `.mrpack`, który da się otworzyć w Modrinth App i Prism, oraz import `.mrpack`.
- **Ustawienia:** RAM, garbage collector (G1 albo ZGC), rozdzielczość, własne argumenty JVM, chowanie launchera w czasie gry.
- **Konsola gry:** logi z gry na żywo.

## 3. Pakiet optymalizacyjny

| Mod | Co robi |
|---|---|
| Sodium | nowy silnik renderowania, zwykle kilka razy więcej FPS |
| Lithium | optymalizacja logiki gry (AI, fizyka, chunki) |
| FerriteCore | mniejsze zużycie RAM |
| ImmediatelyFast | szybsze rysowanie GUI, tekstu i itemów |
| EntityCulling | nie rysuje encji i skrzyń, których nie widać |
| ModernFix | szybsze ładowanie gry i mniej RAM |
| MoreCulling | dodatkowe ukrywanie niewidocznych bloków |
| Dynamic FPS | ogranicza FPS, gdy okno gry jest w tle |
| Krypton | lżejszy stos sieciowy |
| Sodium Extra + Reese's Sodium Options | więcej opcji grafiki i czytelne menu |
| Fabric API | biblioteka wymagana przez większość modów |

Dla każdego modu launcher wybiera najnowszą wersję zgodną z wersją gry. Jeśli jakiegoś modu nie ma dla danej wersji, zostaje pominięty i launcher to zgłasza.

**Flagi JVM:**
- **G1:** krótkie przerwy GC (`MaxGCPauseMillis=50`, większe regiony, `G1NewSizePercent=20`).
- **ZGC:** generacyjny ZGC dla Javy 21 (Minecraft 1.20.5+), praktycznie bez przycinek od GC.

## 4. Architektura

```text
Launcher
├── src
│   ├── shared
│   │   └── types.ts              typy wspólne dla procesu głównego i UI
│   ├── main                      proces główny Electrona (Node.js)
│   │   ├── index.ts              okno aplikacji
│   │   ├── ipc.ts                wszystkie akcje wywoływane z UI
│   │   ├── http.ts               pobieranie z SHA-1, ponowienia, równoległość
│   │   ├── paths.ts              układ folderów z danymi
│   │   ├── auth
│   │   │   ├── microsoft.ts      Microsoft → Xbox Live → XSTS → Minecraft
│   │   │   └── accounts.ts       zaszyfrowane konta
│   │   ├── minecraft
│   │   │   ├── versions.ts       reguły, biblioteki, scalanie wersji z Fabric
│   │   │   ├── installer.ts      pobieranie gry, assetów, natywnych bibliotek
│   │   │   ├── java.ts           pobieranie Javy od Mojang
│   │   │   └── launch.ts         budowanie argumentów startowych
│   │   ├── modrinth
│   │   │   ├── api.ts            wyszukiwanie, zależności, pakiet optymalizacyjny
│   │   │   └── mrpack.ts         eksport i import modpacków
│   │   └── instances
│   │       └── store.ts          instancje, mody, ustawienia
│   ├── preload
│   │   └── index.ts              bezpieczny most window.launcher
│   └── renderer                  UI w React
│       └── src
│           ├── App.tsx
│           ├── pages             Graj, Instancje, Mody, Ustawienia, Konta
│           └── components
└── test                          testy Vitest
```

**Folder z danymi** (`%APPDATA%/MixeLauncher`):

```text
MixeLauncher
├── versions      pliki wersji i client.jar (wspólne dla wszystkich instancji)
├── libraries     biblioteki Mavena
├── assets        indeksy i obiekty assetów
├── runtimes      pobrane Javy
├── instances
│   └── <id>
│       ├── instance.json
│       └── minecraft     folder gry instancji (mods, config, saves...)
├── settings.json
└── accounts.dat  zaszyfrowane konta
```

### Uruchamianie gry krok po kroku

1. Odświeżenie tokenu konta, jeśli wygasa za mniej niż 5 minut.
2. Pobranie JSON-a wersji z manifestu Mojang. Dla Fabric dochodzi profil z `meta.fabricmc.net`, który launcher scala z wersją vanilla: biblioteki Fabric zastępują duplikaty, a argumenty się łączą.
3. Filtrowanie bibliotek po regułach (system, architektura, funkcje) i pobranie ich razem z `client.jar` i configiem logów.
4. Pobranie indeksu assetów i brakujących obiektów (32 naraz).
5. Wypakowanie natywnych bibliotek (`.dll`, `.so`, `.dylib`).
6. Pobranie Javy wskazanej w `javaVersion.component`.
7. Zbudowanie argumentów: pamięć i flagi GC, argumenty JVM z wersji, główna klasa, argumenty gry z podstawionymi `${...}`.
8. Start procesu Javy w folderze instancji i przesyłanie logów do konsoli w UI.

### Logowanie Microsoft

1. Prośba o kod urządzenia: `POST login.microsoftonline.com/consumers/oauth2/v2.0/devicecode` ze scope `XboxLive.signin offline_access`.
2. Użytkownik wpisuje kod na microsoft.com/link, a launcher w tym czasie odpytuje `/token`.
3. Token Microsoft wymieniany jest na token Xbox Live (`user.auth.xboxlive.com`), a ten na token XSTS (`xsts.auth.xboxlive.com`).
4. `POST api.minecraftservices.com/authentication/login_with_xbox` zwraca token Minecraft.
5. Sprawdzenie, czy konto ma grę (`/entitlements/mcstore`), i pobranie profilu (nick i UUID).
6. Przy następnych startach launcher używa refresh tokenu i nie trzeba logować się od nowa.

### Bezpieczeństwo

- Okno ma `contextIsolation`, `sandbox` i wyłączony `nodeIntegration`. UI może tylko wywołać akcje z listy w preloadzie.
- Każdy pobrany plik jest sprawdzany po SHA-1.
- Import `.mrpack` blokuje ścieżki wychodzące poza instancję (`../`) i pobieranie z domen spoza listy dozwolonych (cdn.modrinth.com, github.com, raw.githubusercontent.com, gitlab.com).
- Tokeny nigdy nie trafiają na dysk w postaci jawnej.
- Launcher pobiera pliki gry z oficjalnych serwerów Mojang i niczego nie redystrybuuje.

## 5. Konfiguracja logowania Microsoft (trzeba zrobić raz)

1. Wejdź na portal Azure, otwórz **App registrations** i wybierz **New registration**.
2. Ustaw **Supported account types** na *Personal Microsoft accounts only*.
3. W zakładce **Authentication** włącz **Allow public client flows**, bo to on pozwala logować się kodem urządzenia.
4. Skopiuj **Application (client) ID** i wstaw go do `src/main/auth/microsoft.ts`. Możesz też ustawić zmienną środowiskową `MIXE_CLIENT_ID`.
5. **Ważne:** Mojang wymaga zatwierdzenia nowych aplikacji. Złóż wniosek przez formularz Minecraft o dostęp do API dla swojego Client ID. Dopóki wniosek nie zostanie zatwierdzony, krok `login_with_xbox` zwraca błąd 403 („Invalid app registration”).

## 6. Uruchamianie projektu

```bash
cd Launcher
npm install
npm run dev        # aplikacja w trybie deweloperskim
npm test           # testy
npm run typecheck  # sprawdzenie typów
npm run dist       # instalator Windows (release/)
```

## 7. Co dalej (roadmapa)

- Wsparcie innych loaderów: Quilt, NeoForge i Forge (Forge wymaga uruchomienia instalatora).
- Sprawdzanie aktualizacji modów i aktualizacja jednym kliknięciem.
- Przeglądarka shaderów i resource packów (Modrinth ma je w tym samym API).
- Własny HUD i mody PvP jak w Lunarze, jako mod Fabric od Mixe, instalowany razem z pakietem.
- Zmiana skina z poziomu launchera (API skinów Minecraft).
- Discord Rich Presence, newsy, lista ulubionych serwerów.
- Analiza crashy, która wskazuje mod odpowiedzialny za crash z logu.
- Automatyczne aktualizacje launchera (electron-updater).
- Ikony instancji i osobny RAM dla każdej instancji w UI (pole `memoryMb` już istnieje).
