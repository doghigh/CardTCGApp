# LoreBox Android v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone-capable native Android app for LoreBox: camera capture → Claude-vision identify → Scryfall/eBay valuation → local Room collection, with QR key provisioning from the desktop app.

**Architecture:** Kotlin + Jetpack Compose, MVVM, single Gradle module under `/android`. A `CardRepository` orchestrates an identify→value→save pipeline over Room (SQLite), `IdentifyService` (Anthropic), and `ValuationService` (Scryfall + eBay). Pure parsing functions are separated from network I/O so business logic is JVM-unit-testable. The Room schema mirrors the desktop `cards`/`valuations` tables 1:1 for future LAN sync.

**Tech Stack:** Kotlin, Jetpack Compose, Room, CameraX, Retrofit/OkHttp, kotlinx-serialization, AndroidX Security (EncryptedSharedPreferences), AndroidX Biometric, ZXing (offline QR scan). Desktop pairing dialog: PyQt6 + `qrcode` (already a desktop dependency).

## Global Constraints

- **Branch:** `android-app`. All Android code under `/android`. Desktop `main` stays Store-shippable.
- **minSdk 26, compileSdk 35, targetSdk 35.** Kotlin 2.0.x, AGP 8.5+, JDK 17.
- **Compose** via BOM `2024.09.00`; Material 3.
- **Room** 2.6.1; **CameraX** 1.3.4; **Retrofit** 2.11.0 + **OkHttp** 4.12.0; **kotlinx-serialization-json** 1.7.x; **androidx.security:security-crypto** 1.1.0-alpha06; **androidx.biometric:biometric** 1.1.0; **com.journeyapps:zxing-android-embedded** 4.3.0.
- **Privacy-first:** no analytics SDKs, no Google Play Services dependency, no cloud calls except Anthropic/Scryfall/eBay official APIs. QR scanning is offline (ZXing, not ML Kit).
- **Official APIs only:** Scryfall (Magic, keyless) and eBay Browse API. No scraping.
- **Identify model:** `claude-haiku-4-5-20251001`, `max_tokens=256`. Reuse the desktop `VISION_PROMPT` verbatim.
- **Vision images:** JPEG, longest edge ≤ 1600px, quality 85.
- **eBay valuation:** median of 10%-trimmed price list, then × 0.85. Token cached with 5-min early expiry. Category: sports→`213`, CCG→`183454`, else none.
- **Package name:** `com.lorebox.android`.
- **Encrypted storage** for all API keys (Android Keystore-backed). Never log key values.

---

## File Structure

```
android/
  settings.gradle.kts                      # module include, repos
  build.gradle.kts                         # root build
  gradle.properties                        # JVM/AndroidX flags
  app/
    build.gradle.kts                       # app module deps & android config
    src/main/AndroidManifest.xml           # permissions, app entry
    src/main/java/com/lorebox/android/
      LoreboxApp.kt                         # Application class, DI wiring
      MainActivity.kt                       # ComponentActivity, app-lock gate
      data/
        db/CardEntity.kt                    # Room entity (mirrors desktop cards)
        db/ValuationEntity.kt               # Room entity (mirrors desktop valuations)
        db/CardDao.kt                       # queries: insert/dedupe/search/stats
        db/LoreboxDatabase.kt               # RoomDatabase
        db/CardValidation.kt               # pure validation (mirrors _validate_card)
        keys/KeyStore.kt                    # EncryptedSharedPreferences wrapper
        keys/ProvisioningPayload.kt         # QR JSON model + parse
        image/ImageStore.kt                 # save/load card JPEGs
        identify/IdentifyModels.kt          # request/response DTOs + VISION_PROMPT
        identify/IdentifyParser.kt          # pure: JSON -> CardFields + cleanup
        identify/IdentifyService.kt         # Anthropic network call
        value/ValuationModels.kt            # Valuation, CardFields types
        value/ScryfallParser.kt             # pure: Scryfall JSON -> Valuation
        value/EbayParser.kt                 # pure: Browse JSON -> Valuation (+0.85)
        value/ValuationService.kt           # Scryfall + eBay network + OAuth cache
        CardRepository.kt                   # identify->value->save pipeline + Room
      ui/
        nav/LoreboxNav.kt                   # Compose navigation graph
        capture/CaptureScreen.kt + VM
        review/ReviewScreen.kt + VM
        collection/CollectionScreen.kt + VM
        detail/CardDetailScreen.kt + VM
        settings/SettingsScreen.kt + VM
        pair/PairScreen.kt + VM             # ZXing QR scan / manual entry
        lock/AppLock.kt                     # BiometricPrompt helper
        theme/Theme.kt                      # Compose Material3 dark theme
    src/test/java/com/lorebox/android/      # JVM unit tests
    src/androidTest/java/com/lorebox/android/  # instrumented Room tests
ui/pair_dialog.py                           # DESKTOP: PyQt6 QR pairing dialog
```

---

## Task 1: Gradle scaffold + buildable empty Compose app

**Files:**
- Create: `android/settings.gradle.kts`, `android/build.gradle.kts`, `android/gradle.properties`
- Create: `android/app/build.gradle.kts`
- Create: `android/app/src/main/AndroidManifest.xml`
- Create: `android/app/src/main/java/com/lorebox/android/MainActivity.kt`
- Create: `android/app/src/main/java/com/lorebox/android/ui/theme/Theme.kt`
- Create: `android/.gitignore`

**Interfaces:**
- Produces: a buildable Gradle project; `MainActivity` showing a Compose "LoreBox" placeholder.

- [ ] **Step 1: Create `android/.gitignore`**

```
.gradle/
build/
local.properties
*.iml
.idea/
captures/
```

- [ ] **Step 2: Create `android/settings.gradle.kts`**

```kotlin
pluginManagement {
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
}
rootProject.name = "LoreBox"
include(":app")
```

- [ ] **Step 3: Create `android/build.gradle.kts`**

```kotlin
plugins {
    id("com.android.application") version "8.5.2" apply false
    id("org.jetbrains.kotlin.android") version "2.0.20" apply false
    id("org.jetbrains.kotlin.plugin.serialization") version "2.0.20" apply false
    id("com.google.devtools.ksp") version "2.0.20-1.0.25" apply false
}
```

- [ ] **Step 4: Create `android/gradle.properties`**

```
org.gradle.jvmargs=-Xmx2048m
android.useAndroidX=true
kotlin.code.style=official
android.nonTransitiveRClass=true
```

- [ ] **Step 5: Create `android/app/build.gradle.kts`**

```kotlin
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.serialization")
    id("com.google.devtools.ksp")
}

android {
    namespace = "com.lorebox.android"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.lorebox.android"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    buildFeatures { compose = true }
    composeOptions { kotlinCompilerExtensionVersion = "1.5.14" }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildTypes {
        release { isMinifyEnabled = false }
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.09.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.activity:activity-compose:1.9.2")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.6")
    implementation("androidx.navigation:navigation-compose:2.8.0")

    // Room
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    ksp("androidx.room:room-compiler:2.6.1")

    // Networking + serialization
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.1")
    implementation("com.jakewharton.retrofit:retrofit2-kotlinx-serialization-converter:1.0.0")

    // CameraX
    implementation("androidx.camera:camera-core:1.3.4")
    implementation("androidx.camera:camera-camera2:1.3.4")
    implementation("androidx.camera:camera-lifecycle:1.3.4")
    implementation("androidx.camera:camera-view:1.3.4")

    // Security, biometric, QR
    implementation("androidx.security:security-crypto:1.1.0-alpha06")
    implementation("androidx.biometric:biometric:1.1.0")
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")

    // Image loading
    implementation("io.coil-kt:coil-compose:2.7.0")

    // Tests
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.1")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.room:room-testing:2.6.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
}
```

- [ ] **Step 6: Create `android/app/src/main/java/com/lorebox/android/ui/theme/Theme.kt`**

```kotlin
package com.lorebox.android.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val DarkColors = darkColorScheme(
    primary = Color(0xFF7C4DFF),
    secondary = Color(0xFFB39DDB),
)
private val LightColors = lightColorScheme(
    primary = Color(0xFF6200EE),
    secondary = Color(0xFF7C4DFF),
)

@Composable
fun LoreboxTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        content = content,
    )
}
```

- [ ] **Step 7: Create `android/app/src/main/java/com/lorebox/android/MainActivity.kt`**

```kotlin
package com.lorebox.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import com.lorebox.android.ui.theme.LoreboxTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            LoreboxTheme { Surface { Text("LoreBox") } }
        }
    }
}
```

- [ ] **Step 8: Create `android/app/src/main/AndroidManifest.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.CAMERA" />
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-feature android:name="android.hardware.camera.any" android:required="false" />

    <application
        android:name=".LoreboxApp"
        android:label="LoreBox"
        android:allowBackup="false"
        android:theme="@style/Theme.Material3.DynamicColors.DayNight">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

- [ ] **Step 9: Create placeholder `LoreboxApp.kt`** (replaced in Task 9)

```kotlin
package com.lorebox.android

import android.app.Application

class LoreboxApp : Application()
```

- [ ] **Step 10: Build to verify the project assembles**

Run: `cd android && ./gradlew :app:assembleDebug`
Expected: `BUILD SUCCESSFUL`. (On Windows use `gradlew.bat`. If the Gradle wrapper is absent, run `gradle wrapper --gradle-version 8.9` once first.)

- [ ] **Step 11: Commit**

```bash
git add android/
git commit -m "feat(android): gradle scaffold + empty Compose app"
```

---

## Task 2: Card field validation (pure, TDD)

**Files:**
- Create: `android/app/src/main/java/com/lorebox/android/data/db/CardValidation.kt`
- Test: `android/app/src/test/java/com/lorebox/android/data/db/CardValidationTest.kt`

**Interfaces:**
- Produces: `data class CardInput(...)` and `fun validateCard(input: CardInput): CardInput`
  mirroring desktop `_validate_card` (name≤200 default "Unknown"; year 1800..currentYear+1 or null; quantity 1..9999; prices 0..1_000_000 rounded 2dp; conditionScore 0..100 or null; foil→0/1; bounded text fields; notes≤2000).

- [ ] **Step 1: Write the failing test**

```kotlin
package com.lorebox.android.data.db

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CardValidationTest {
    @Test fun blankNameBecomesUnknown() {
        assertEquals("Unknown", validateCard(CardInput(name = "   ")).name)
    }
    @Test fun nameTruncatedTo200() {
        val long = "x".repeat(250)
        assertEquals(200, validateCard(CardInput(name = long)).name.length)
    }
    @Test fun yearOutOfRangeBecomesNull() {
        assertNull(validateCard(CardInput(name = "A", year = 1700)).year)
        assertNull(validateCard(CardInput(name = "A", year = 4000)).year)
        assertEquals(1994, validateCard(CardInput(name = "A", year = 1994)).year)
    }
    @Test fun quantityClamped() {
        assertEquals(1, validateCard(CardInput(name = "A", quantity = 0)).quantity)
        assertEquals(9999, validateCard(CardInput(name = "A", quantity = 50000)).quantity)
    }
    @Test fun negativePriceClampedToZero() {
        assertEquals(0.0, validateCard(CardInput(name = "A", estimatedValue = -5.0)).estimatedValue, 0.001)
    }
    @Test fun foilCoercedToBooleanInt() {
        assertEquals(1, validateCard(CardInput(name = "A", foil = 1)).foil)
        assertEquals(0, validateCard(CardInput(name = "A", foil = 0)).foil)
    }
    @Test fun blankSetBecomesNull() {
        assertNull(validateCard(CardInput(name = "A", setName = "  ")).setName)
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./gradlew :app:testDebugUnitTest --tests "*CardValidationTest"`
Expected: FAIL (unresolved reference `validateCard` / `CardInput`).

- [ ] **Step 3: Write minimal implementation**

```kotlin
package com.lorebox.android.data.db

import java.util.Calendar
import kotlin.math.max
import kotlin.math.min

data class CardInput(
    val name: String = "",
    val setName: String? = null,
    val cardNumber: String? = null,
    val rarity: String? = null,
    val game: String? = null,
    val year: Int? = null,
    val language: String? = "English",
    val foil: Int = 0,
    val frontScanPath: String? = null,
    val backScanPath: String? = null,
    val conditionGrade: String? = null,
    val conditionScore: Double? = null,
    val defectsJson: String? = null,
    val estimatedValue: Double = 0.0,
    val purchasePrice: Double = 0.0,
    val purchaseDate: String? = null,
    val notes: String? = null,
    val quantity: Int = 1,
)

private fun bounded(value: String?, maxLen: Int): String? {
    val cleaned = value?.trim()?.take(maxLen)
    return if (cleaned.isNullOrEmpty()) null else cleaned
}

private fun round2(v: Double) = Math.round(v * 100.0) / 100.0

fun validateCard(input: CardInput): CardInput {
    val currentYear = Calendar.getInstance().get(Calendar.YEAR)
    val name = input.name.trim().take(200).ifEmpty { "Unknown" }
    val year = input.year?.takeIf { it in 1800..(currentYear + 1) }
    val quantity = max(1, min(9999, input.quantity))
    val estimatedValue = round2(max(0.0, min(1_000_000.0, input.estimatedValue)))
    val purchasePrice = round2(max(0.0, min(1_000_000.0, input.purchasePrice)))
    val conditionScore = input.conditionScore?.let {
        Math.round(max(0.0, min(100.0, it)) * 10.0) / 10.0
    }
    return input.copy(
        name = name,
        setName = bounded(input.setName, 200),
        cardNumber = bounded(input.cardNumber, 50),
        rarity = bounded(input.rarity, 50),
        game = bounded(input.game, 100),
        language = bounded(input.language, 50) ?: "English",
        conditionGrade = bounded(input.conditionGrade, 50),
        notes = input.notes?.trim()?.take(2000)?.ifEmpty { null },
        year = year,
        quantity = quantity,
        estimatedValue = estimatedValue,
        purchasePrice = purchasePrice,
        conditionScore = conditionScore,
        foil = if (input.foil != 0) 1 else 0,
    )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./gradlew :app:testDebugUnitTest --tests "*CardValidationTest"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/java/com/lorebox/android/data/db/CardValidation.kt android/app/src/test/java/com/lorebox/android/data/db/CardValidationTest.kt
git commit -m "feat(android): card field validation mirroring desktop"
```

---

## Task 3: Room entities, DAO, database + dedupe (instrumented TDD)

**Files:**
- Create: `data/db/CardEntity.kt`, `data/db/ValuationEntity.kt`, `data/db/CardDao.kt`, `data/db/LoreboxDatabase.kt`
- Test: `android/app/src/androidTest/java/com/lorebox/android/data/db/CardDaoTest.kt`

**Interfaces:**
- Consumes: `CardInput`, `validateCard` (Task 2).
- Produces:
  - `CardEntity` with all desktop columns; PK `id: Long autoGenerate`.
  - `CardDao`: `suspend fun insert(card: CardEntity): Long`, `suspend fun findDuplicateId(name,setName,cardNumber,game,foil): Long?`, `suspend fun bumpQuantity(id: Long, by: Int)`, `fun observeAll(): Flow<List<CardEntity>>`, `suspend fun search(term: String): List<CardEntity>`, `suspend fun getById(id: Long): CardEntity?`, `suspend fun delete(id: Long)`, valuation insert/list.
  - `LoreboxDatabase.get(context): LoreboxDatabase`.

- [ ] **Step 1: Create `CardEntity.kt`**

```kotlin
package com.lorebox.android.data.db

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "cards")
data class CardEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val setName: String? = null,
    val cardNumber: String? = null,
    val rarity: String? = null,
    val game: String? = null,
    val year: Int? = null,
    val language: String? = "English",
    val foil: Int = 0,
    val frontScanPath: String? = null,
    val backScanPath: String? = null,
    val conditionGrade: String? = null,
    val conditionScore: Double? = null,
    val defectsJson: String? = null,
    val estimatedValue: Double = 0.0,
    val purchasePrice: Double = 0.0,
    val purchaseDate: String? = null,
    val notes: String? = null,
    val quantity: Int = 1,
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis(),
)
```

- [ ] **Step 2: Create `ValuationEntity.kt`**

```kotlin
package com.lorebox.android.data.db

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "valuations",
    foreignKeys = [ForeignKey(
        entity = CardEntity::class, parentColumns = ["id"],
        childColumns = ["cardId"], onDelete = ForeignKey.CASCADE)],
    indices = [Index("cardId")],
)
data class ValuationEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val cardId: Long,
    val source: String,
    val value: Double,
    val currency: String = "USD",
    val url: String? = null,
    val fetchedAt: Long = System.currentTimeMillis(),
)
```

- [ ] **Step 3: Create `CardDao.kt`**

```kotlin
package com.lorebox.android.data.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface CardDao {
    @Insert suspend fun insert(card: CardEntity): Long
    @Insert suspend fun insertValuation(v: ValuationEntity): Long

    @Query("""
        SELECT id FROM cards
        WHERE LOWER(IFNULL(name,'')) = LOWER(IFNULL(:name,''))
          AND IFNULL(setName,'')    = IFNULL(:setName,'')
          AND IFNULL(cardNumber,'') = IFNULL(:cardNumber,'')
          AND IFNULL(game,'')       = IFNULL(:game,'')
          AND IFNULL(foil,0)        = IFNULL(:foil,0)
        ORDER BY id ASC LIMIT 1
    """)
    suspend fun findDuplicateId(
        name: String?, setName: String?, cardNumber: String?, game: String?, foil: Int
    ): Long?

    @Query("UPDATE cards SET quantity = quantity + :by, updatedAt = :now WHERE id = :id")
    suspend fun bumpQuantity(id: Long, by: Int, now: Long = System.currentTimeMillis())

    @Query("SELECT * FROM cards ORDER BY updatedAt DESC, id ASC")
    fun observeAll(): Flow<List<CardEntity>>

    @Query("""
        SELECT * FROM cards
        WHERE name LIKE '%' || :term || '%' OR setName LIKE '%' || :term || '%'
           OR game LIKE '%' || :term || '%' OR cardNumber LIKE '%' || :term || '%'
        ORDER BY updatedAt DESC, id ASC
    """)
    suspend fun search(term: String): List<CardEntity>

    @Query("SELECT * FROM cards WHERE id = :id") suspend fun getById(id: Long): CardEntity?
    @Query("DELETE FROM cards WHERE id = :id") suspend fun delete(id: Long)
    @Query("SELECT * FROM valuations WHERE cardId = :cardId ORDER BY fetchedAt DESC")
    suspend fun valuationsFor(cardId: Long): List<ValuationEntity>
}
```

- [ ] **Step 4: Create `LoreboxDatabase.kt`**

```kotlin
package com.lorebox.android.data.db

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(entities = [CardEntity::class, ValuationEntity::class], version = 1, exportSchema = false)
abstract class LoreboxDatabase : RoomDatabase() {
    abstract fun cardDao(): CardDao
    companion object {
        @Volatile private var instance: LoreboxDatabase? = null
        fun get(context: Context): LoreboxDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(
                context.applicationContext, LoreboxDatabase::class.java, "lorebox.db"
            ).build().also { instance = it }
        }
    }
}
```

- [ ] **Step 5: Write the failing instrumented test**

```kotlin
package com.lorebox.android.data.db

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CardDaoTest {
    private lateinit var db: LoreboxDatabase
    private lateinit var dao: CardDao

    @Before fun setup() {
        db = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(), LoreboxDatabase::class.java
        ).build()
        dao = db.cardDao()
    }
    @After fun teardown() = db.close()

    @Test fun insertAndFindDuplicate() = runBlocking {
        val card = CardEntity(name = "Elvish Farmer", setName = "Fallen Empires", game = "Magic: The Gathering")
        val id = dao.insert(card)
        assertTrue(id > 0)
        val dup = dao.findDuplicateId("elvish farmer", "Fallen Empires", null, "Magic: The Gathering", 0)
        assertEquals(id, dup)
    }

    @Test fun searchMatchesName() = runBlocking {
        dao.insert(CardEntity(name = "Black Lotus", game = "Magic: The Gathering"))
        assertEquals(1, dao.search("lotus").size)
        assertEquals(0, dao.search("zzz").size)
    }
}
```

- [ ] **Step 6: Run test to verify it fails, then passes after build**

Run: `./gradlew :app:connectedDebugAndroidTest --tests "*CardDaoTest"` (requires a connected device/emulator).
Expected: compiles and PASSES (this task creates all referenced types). If Room codegen errors, fix the entity/DAO before proceeding.

- [ ] **Step 7: Commit**

```bash
git add android/app/src/main/java/com/lorebox/android/data/db/ android/app/src/androidTest/
git commit -m "feat(android): Room schema, DAO, dedupe + search"
```

---

## Task 4: Identify parser (pure, TDD)

**Files:**
- Create: `data/identify/IdentifyModels.kt`, `data/identify/IdentifyParser.kt`
- Test: `android/app/src/test/java/com/lorebox/android/data/identify/IdentifyParserTest.kt`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `data class CardFields(name: String?, setName: String?, cardNumber: String?, rarity: String?, year: Int?, game: String?)`
  - `const val VISION_PROMPT: String` (verbatim from `core/identifier.py`).
  - `fun parseIdentifyJson(raw: String): CardFields?` — strips ```` ``` ```` fences, parses JSON, applies the desktop cleanup (game-name never leaks into setName; cardNumber coerced to string; year to Int). Returns null on malformed input.

- [ ] **Step 1: Write the failing test**

```kotlin
package com.lorebox.android.data.identify

import org.junit.Assert.*
import org.junit.Test

class IdentifyParserTest {
    @Test fun parsesPlainJson() {
        val raw = """{"name":"Elvish Farmer","set_name":"Fallen Empires","card_number":null,"rarity":"Common","year":1994,"game":"Magic: The Gathering"}"""
        val f = parseIdentifyJson(raw)!!
        assertEquals("Elvish Farmer", f.name)
        assertEquals("Fallen Empires", f.setName)
        assertEquals(1994, f.year)
        assertEquals("Common", f.rarity)
    }
    @Test fun stripsMarkdownFences() {
        val raw = "```json\n{\"name\":\"Black Lotus\",\"game\":\"Magic: The Gathering\"}\n```"
        assertEquals("Black Lotus", parseIdentifyJson(raw)!!.name)
    }
    @Test fun gameNameNeverLeaksIntoSet() {
        val raw = """{"name":"X","set_name":"Magic: The Gathering","game":"Magic: The Gathering"}"""
        assertNull(parseIdentifyJson(raw)!!.setName)
    }
    @Test fun cardNumberCoercedToString() {
        val raw = """{"name":"X","card_number":86,"game":"Magic: The Gathering"}"""
        assertEquals("86", parseIdentifyJson(raw)!!.cardNumber)
    }
    @Test fun malformedReturnsNull() {
        assertNull(parseIdentifyJson("not json"))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./gradlew :app:testDebugUnitTest --tests "*IdentifyParserTest"`
Expected: FAIL (unresolved `parseIdentifyJson`).

- [ ] **Step 3: Create `IdentifyModels.kt`**

```kotlin
package com.lorebox.android.data.identify

data class CardFields(
    val name: String? = null,
    val setName: String? = null,
    val cardNumber: String? = null,
    val rarity: String? = null,
    val year: Int? = null,
    val game: String? = null,
)

// Verbatim from desktop core/identifier.py VISION_PROMPT.
const val VISION_PROMPT: String = """You are a trading card expert. Examine this card image and extract the fields below.
Respond with ONLY a JSON object — no markdown, no commentary.

Fields:
- name: the card's TITLE — the text in the title bar at the very TOP of the card.
    * Magic cards: the card name printed at the top. Do NOT use the type line
      (e.g. "Summon Creature", "Summon Elf", "Summon Wall", "Creature — Elf",
      "Artifact", "Instant"). The type line sits in the MIDDLE of the card,
      below the art, and is NEVER the name.
    * Sports cards: the player's name.
- set_name: the specific set / expansion name or set code (e.g. "Tempest",
    "Fallen Empires", "FEM", "Topps", "Fleer"). If you cannot clearly identify
    the set, use null. NEVER put the game's name (e.g. "Magic: The Gathering")
    in this field.
- card_number: the collector number exactly as printed (often a bottom corner,
    e.g. "86", "011/011", "4/5"), else null.
- rarity: rarity if shown (Common / Uncommon / Rare / Mythic, or a sports
    insert label), else null.
- year: 4-digit year as an integer if visible (often in the bottom copyright
    line), else null.
- game: one of "Baseball", "Basketball", "Football", "Hockey",
    "Magic: The Gathering", "Pokémon", "Yu-Gi-Oh!", "One Piece", "Lorcana",
    "Sports Cards", "Non-Sport" (entertainment/TV/movie cards such as Star Wars,
    Garbage Pail Kids, Marvel), or "Other".

Important:
- Older Magic cards (pre-2003) print the type as "Summon <type>". Ignore that
  line completely when choosing the name — read the title bar at the top.
- A token's name is its creature/permanent name at the top (e.g. "Plant").
- If a field is unreadable or absent, use null rather than guessing.

Example: {"name": "Elvish Farmer", "set_name": "Fallen Empires", "card_number": null, "rarity": "Common", "year": 1994, "game": "Magic: The Gathering"}"""
```

- [ ] **Step 4: Create `IdentifyParser.kt`**

```kotlin
package com.lorebox.android.data.identify

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull

private val GAME_NAMES = setOf(
    "magic: the gathering", "magic the gathering", "magic", "mtg",
    "pokemon", "pokémon", "yu-gi-oh!", "yugioh",
)

fun parseIdentifyJson(raw: String): CardFields? {
    val cleaned = raw.trim()
        .replace(Regex("^```[a-zA-Z]*\\n?"), "")
        .replace(Regex("\\n?```$"), "")
        .trim()
    return try {
        val obj = Json.parseToJsonElement(cleaned).jsonObject
        fun str(key: String) = obj[key]?.jsonPrimitive?.contentOrNull?.takeIf { it.isNotBlank() && it != "null" }
        var setName = str("set_name")
        if (setName != null && setName.trim().lowercase() in GAME_NAMES) setName = null
        val cardNumber = obj["card_number"]?.jsonPrimitive?.contentOrNull
            ?.takeIf { it.isNotBlank() && it != "null" }
        val year = obj["year"]?.jsonPrimitive?.intOrNull
        CardFields(
            name = str("name"), setName = setName, cardNumber = cardNumber,
            rarity = str("rarity"), year = year, game = str("game"),
        )
    } catch (e: Exception) {
        null
    }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./gradlew :app:testDebugUnitTest --tests "*IdentifyParserTest"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/java/com/lorebox/android/data/identify/ android/app/src/test/java/com/lorebox/android/data/identify/
git commit -m "feat(android): vision-identify JSON parser + prompt"
```

---

## Task 5: Scryfall parser (pure, TDD)

**Files:**
- Create: `data/value/ValuationModels.kt`, `data/value/ScryfallParser.kt`
- Test: `android/app/src/test/java/com/lorebox/android/data/value/ScryfallParserTest.kt`

**Interfaces:**
- Produces:
  - `data class Valuation(source: String, value: Double, low: Double, high: Double, sample: Int, query: String)`
  - `fun isMtg(game: String?): Boolean`
  - `fun parseScryfallCard(json: String, name: String): Valuation?` — reads `prices.usd|usd_foil|usd_etched`, returns null if none > 0; source `"Scryfall (SET)"`.

- [ ] **Step 1: Write the failing test**

```kotlin
package com.lorebox.android.data.value

import org.junit.Assert.*
import org.junit.Test

class ScryfallParserTest {
    @Test fun parsesUsdPrice() {
        val json = """{"set":"fem","prices":{"usd":"2.50","usd_foil":null}}"""
        val v = parseScryfallCard(json, "Elvish Farmer")!!
        assertEquals(2.50, v.value, 0.001)
        assertTrue(v.source.contains("FEM"))
    }
    @Test fun fallsBackToFoil() {
        val json = """{"set":"lea","prices":{"usd":null,"usd_foil":"10.00"}}"""
        assertEquals(10.0, parseScryfallCard(json, "X")!!.value, 0.001)
    }
    @Test fun nullWhenNoPrice() {
        assertNull(parseScryfallCard("""{"set":"lea","prices":{"usd":null}}""", "X"))
    }
    @Test fun isMtgDetection() {
        assertTrue(isMtg("Magic: The Gathering"))
        assertTrue(isMtg("MTG"))
        assertFalse(isMtg("Pokémon"))
        assertFalse(isMtg(null))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./gradlew :app:testDebugUnitTest --tests "*ScryfallParserTest"`
Expected: FAIL.

- [ ] **Step 3: Create `ValuationModels.kt`**

```kotlin
package com.lorebox.android.data.value

data class Valuation(
    val source: String,
    val value: Double,
    val low: Double,
    val high: Double,
    val sample: Int,
    val query: String,
)
```

- [ ] **Step 4: Create `ScryfallParser.kt`**

```kotlin
package com.lorebox.android.data.value

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.contentOrNull

fun isMtg(game: String?): Boolean {
    val g = game?.lowercase() ?: return false
    return "magic" in g || "mtg" in g
}

fun parseScryfallCard(json: String, name: String): Valuation? {
    return try {
        val obj = Json.parseToJsonElement(json).jsonObject
        val prices = obj["prices"]?.jsonObject
        val price = listOf("usd", "usd_foil", "usd_etched")
            .firstNotNullOfOrNull { prices?.get(it)?.jsonPrimitive?.contentOrNull?.toDoubleOrNull() }
            ?.takeIf { it > 0 } ?: return null
        val set = (obj["set"]?.jsonPrimitive?.contentOrNull ?: "").uppercase()
        val rounded = Math.round(price * 100.0) / 100.0
        Valuation(
            source = if (set.isNotEmpty()) "Scryfall ($set)" else "Scryfall",
            value = rounded, low = rounded, high = rounded, sample = 1, query = name,
        )
    } catch (e: Exception) {
        null
    }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./gradlew :app:testDebugUnitTest --tests "*ScryfallParserTest"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/java/com/lorebox/android/data/value/ValuationModels.kt android/app/src/main/java/com/lorebox/android/data/value/ScryfallParser.kt android/app/src/test/java/com/lorebox/android/data/value/ScryfallParserTest.kt
git commit -m "feat(android): Scryfall price parser"
```

---

## Task 6: eBay Browse parser + query builder (pure, TDD)

**Files:**
- Create: `data/value/EbayParser.kt`
- Test: `android/app/src/test/java/com/lorebox/android/data/value/EbayParserTest.kt`

**Interfaces:**
- Produces:
  - `fun buildEbayQuery(name: String, setName: String?, game: String?): String`
  - `fun ebayCategory(game: String?): String?` (sports→"213", CCG→"183454", else null)
  - `fun parseBrowseResponse(json: String, query: String): Valuation?` — collects `itemSummaries[].price.value` in (0.25, 50000), sorts, trims 10% each end, median; source `"eBay Browse (active)"`.
  - `fun applyActiveDiscount(v: Valuation): Valuation` — value × 0.85, source `"eBay Browse (active, est.)"`.

- [ ] **Step 1: Write the failing test**

```kotlin
package com.lorebox.android.data.value

import org.junit.Assert.*
import org.junit.Test

class EbayParserTest {
    @Test fun medianOfTrimmedPrices() {
        val items = (1..11).joinToString(",") { """{"price":{"value":"$it.00"}}""" }
        val json = """{"itemSummaries":[$items]}"""
        val v = parseBrowseResponse(json, "q")!!
        assertEquals(6.0, v.value, 0.001) // median of 1..11
    }
    @Test fun ignoresOutOfRangePrices() {
        val json = """{"itemSummaries":[{"price":{"value":"0.10"}},{"price":{"value":"5.00"}}]}"""
        assertEquals(5.0, parseBrowseResponse(json, "q")!!.value, 0.001)
    }
    @Test fun emptyReturnsNull() {
        assertNull(parseBrowseResponse("""{"itemSummaries":[]}""", "q"))
    }
    @Test fun discountApplied() {
        val v = Valuation("eBay Browse (active)", 10.0, 5.0, 20.0, 3, "q")
        assertEquals(8.5, applyActiveDiscount(v).value, 0.001)
    }
    @Test fun categoryMapping() {
        assertEquals("213", ebayCategory("Baseball"))
        assertEquals("183454", ebayCategory("Pokémon"))
        assertNull(ebayCategory("Non-Sport"))
    }
    @Test fun queryIncludesCardKeyword() {
        assertTrue(buildEbayQuery("Charizard", "Base Set", "Pokémon").endsWith("card"))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./gradlew :app:testDebugUnitTest --tests "*EbayParserTest"`
Expected: FAIL.

- [ ] **Step 3: Create `EbayParser.kt`**

```kotlin
package com.lorebox.android.data.value

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.contentOrNull

fun ebayCategory(game: String?): String? {
    val g = game?.lowercase() ?: return null
    val sports = setOf("baseball", "basketball", "football", "hockey", "sports cards")
    val tcg = listOf("magic", "mtg", "pokémon", "pokemon", "yu-gi-oh", "yugioh",
        "one piece", "lorcana", "flesh and blood")
    return when {
        g in sports -> "213"
        tcg.any { it in g } -> "183454"
        else -> null
    }
}

fun buildEbayQuery(name: String, setName: String?, game: String?): String {
    val parts = mutableListOf(name)
    if (!setName.isNullOrBlank() && setName.lowercase() !in name.lowercase()) parts.add(setName)
    if (!game.isNullOrBlank()) {
        listOf("Pokémon", "Pokemon", "Magic", "Yu-Gi-Oh",
            "Baseball", "Basketball", "Football", "Hockey").firstOrNull {
            it.lowercase() in game.lowercase()
        }?.let { parts.add(it) }
    }
    parts.add("card")
    return parts.joinToString(" ")
}

fun parseBrowseResponse(json: String, query: String): Valuation? {
    return try {
        val items = Json.parseToJsonElement(json).jsonObject["itemSummaries"]?.jsonArray ?: return null
        val prices = items.mapNotNull {
            it.jsonObject["price"]?.jsonObject?.get("value")?.jsonPrimitive?.contentOrNull?.toDoubleOrNull()
        }.filter { it > 0.25 && it < 50_000 }.sorted()
        if (prices.isEmpty()) return null
        val trim = maxOf(1, prices.size / 10)
        val trimmed = prices.drop(trim).dropLast(trim).ifEmpty { prices }
        val median = trimmed.let {
            val mid = it.size / 2
            if (it.size % 2 == 0) (it[mid - 1] + it[mid]) / 2 else it[mid]
        }
        Valuation(
            source = "eBay Browse (active)",
            value = Math.round(median * 100.0) / 100.0,
            low = trimmed.first(), high = trimmed.last(), sample = trimmed.size, query = query,
        )
    } catch (e: Exception) {
        null
    }
}

fun applyActiveDiscount(v: Valuation): Valuation =
    v.copy(value = Math.round(v.value * 0.85 * 100.0) / 100.0, source = "eBay Browse (active, est.)")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./gradlew :app:testDebugUnitTest --tests "*EbayParserTest"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/java/com/lorebox/android/data/value/EbayParser.kt android/app/src/test/java/com/lorebox/android/data/value/EbayParserTest.kt
git commit -m "feat(android): eBay Browse parser, query builder, discount"
```

---

## Task 7: KeyStore + provisioning payload (TDD where pure)

**Files:**
- Create: `data/keys/ProvisioningPayload.kt`, `data/keys/KeyStore.kt`
- Test: `android/app/src/test/java/com/lorebox/android/data/keys/ProvisioningPayloadTest.kt`

**Interfaces:**
- Produces:
  - `@Serializable data class ProvisioningPayload(anthropicKey, ebayAppId, ebayCertId)` (all nullable strings) + `fun parseProvisioning(qr: String): ProvisioningPayload?`.
  - `class KeyStore(context)` with `var anthropicKey: String?`, `var ebayAppId: String?`, `var ebayCertId: String?`, `var appLockEnabled: Boolean`, backed by EncryptedSharedPreferences. Plus `fun importFrom(p: ProvisioningPayload)`.

- [ ] **Step 1: Write the failing test (parser only — pure)**

```kotlin
package com.lorebox.android.data.keys

import org.junit.Assert.*
import org.junit.Test

class ProvisioningPayloadTest {
    @Test fun parsesValidPayload() {
        val qr = """{"anthropicKey":"sk-abc","ebayAppId":"app1","ebayCertId":"cert1"}"""
        val p = parseProvisioning(qr)!!
        assertEquals("sk-abc", p.anthropicKey)
        assertEquals("app1", p.ebayAppId)
    }
    @Test fun parsesPartialPayload() {
        val p = parseProvisioning("""{"anthropicKey":"sk-only"}""")!!
        assertEquals("sk-only", p.anthropicKey)
        assertNull(p.ebayAppId)
    }
    @Test fun malformedReturnsNull() {
        assertNull(parseProvisioning("garbage"))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./gradlew :app:testDebugUnitTest --tests "*ProvisioningPayloadTest"`
Expected: FAIL.

- [ ] **Step 3: Create `ProvisioningPayload.kt`**

```kotlin
package com.lorebox.android.data.keys

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

@Serializable
data class ProvisioningPayload(
    val anthropicKey: String? = null,
    val ebayAppId: String? = null,
    val ebayCertId: String? = null,
)

private val json = Json { ignoreUnknownKeys = true }

fun parseProvisioning(qr: String): ProvisioningPayload? = try {
    json.decodeFromString<ProvisioningPayload>(qr.trim())
} catch (e: Exception) { null }
```

- [ ] **Step 4: Create `KeyStore.kt`**

```kotlin
package com.lorebox.android.data.keys

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class KeyStore(context: Context) {
    private val prefs: SharedPreferences = run {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build()
        EncryptedSharedPreferences.create(
            context, "lorebox_keys", masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    private fun str(key: String): String? = prefs.getString(key, null)?.ifBlank { null }
    private fun set(key: String, value: String?) =
        prefs.edit().apply { if (value.isNullOrBlank()) remove(key) else putString(key, value) }.apply()

    var anthropicKey: String?
        get() = str("anthropic_key"); set(v) = set("anthropic_key", v)
    var ebayAppId: String?
        get() = str("ebay_app_id"); set(v) = set("ebay_app_id", v)
    var ebayCertId: String?
        get() = str("ebay_cert_id"); set(v) = set("ebay_cert_id", v)
    var appLockEnabled: Boolean
        get() = prefs.getBoolean("app_lock", false)
        set(v) = prefs.edit().putBoolean("app_lock", v).apply()

    fun importFrom(p: ProvisioningPayload) {
        p.anthropicKey?.let { anthropicKey = it }
        p.ebayAppId?.let { ebayAppId = it }
        p.ebayCertId?.let { ebayCertId = it }
    }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./gradlew :app:testDebugUnitTest --tests "*ProvisioningPayloadTest"`
Expected: PASS. (KeyStore itself is exercised via instrumented use in Task 9+; no unit test for the Android-only crypto class.)

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/java/com/lorebox/android/data/keys/
git commit -m "feat(android): encrypted key store + QR provisioning payload"
```

---

## Task 8: Network services (Identify, Scryfall, eBay) + ImageStore

**Files:**
- Create: `data/identify/IdentifyService.kt`, `data/value/ValuationService.kt`, `data/image/ImageStore.kt`
- Test: `android/app/src/test/java/com/lorebox/android/data/value/ValuationServiceOAuthTest.kt`

**Interfaces:**
- Consumes: `KeyStore`, `parseIdentifyJson`, `VISION_PROMPT`, `parseScryfallCard`, `parseBrowseResponse`, `applyActiveDiscount`, `buildEbayQuery`, `ebayCategory`, `isMtg`.
- Produces:
  - `class IdentifyService(keyStore, client=OkHttpClient)` → `suspend fun identify(frontJpeg: ByteArray, backJpeg: ByteArray?): CardFields?` (returns null if no key or call fails).
  - `class ValuationService(keyStore, client)` → `suspend fun value(name, setName, game): Valuation?`; internal `suspend fun ebayToken(): String?` with 5-min-early cache.
  - `class ImageStore(context)` → `fun save(bytes: ByteArray, prefix: String): String` (returns absolute path), `fun downscaleJpeg(bytes: ByteArray): ByteArray` (longest edge ≤1600, q85).

- [ ] **Step 1: Write the failing OAuth-cache test**

```kotlin
package com.lorebox.android.data.value

import org.junit.Assert.*
import org.junit.Test

class ValuationServiceOAuthTest {
    @Test fun tokenIsExpiredWhenPastExpiry() {
        assertTrue(isTokenExpired(now = 1000L, expiryEpochMs = 900L))
        assertFalse(isTokenExpired(now = 1000L, expiryEpochMs = 2000L))
    }
    @Test fun expiryAppliesFiveMinuteEarlyMargin() {
        // expires_in=7200s -> expiry = issued + (7200-300)*1000
        assertEquals(0L + 6_900_000L, computeExpiry(issuedAtMs = 0L, expiresInSec = 7200))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./gradlew :app:testDebugUnitTest --tests "*ValuationServiceOAuthTest"`
Expected: FAIL (unresolved `isTokenExpired` / `computeExpiry`).

- [ ] **Step 3: Create `ValuationService.kt`** (pure helpers at top so the test passes; network methods below)

```kotlin
package com.lorebox.android.data.value

import com.lorebox.android.data.keys.KeyStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.FormBody
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import java.util.Base64

fun isTokenExpired(now: Long, expiryEpochMs: Long): Boolean = now >= expiryEpochMs
fun computeExpiry(issuedAtMs: Long, expiresInSec: Int): Long =
    issuedAtMs + (expiresInSec - 300).toLong() * 1000L

private const val SCRYFALL_NAMED = "https://api.scryfall.com/cards/named"
private const val EBAY_OAUTH = "https://api.ebay.com/identity/v1/oauth2/token"
private const val EBAY_BROWSE = "https://api.ebay.com/buy/browse/v1/item_summary/search"
private const val BROWSE_SCOPE = "https://api.ebay.com/oauth/api_scope"

class ValuationService(
    private val keys: KeyStore,
    private val client: OkHttpClient = OkHttpClient(),
) {
    private var token: String? = null
    private var tokenExpiry: Long = 0L

    suspend fun value(name: String, setName: String?, game: String?): Valuation? =
        withContext(Dispatchers.IO) {
            if (name.isBlank()) return@withContext null
            if (isMtg(game)) scryfall(name, setName)?.let { return@withContext it }
            ebayBrowse(name, setName, game)?.let { applyActiveDiscount(it) }
        }

    private fun scryfall(name: String, setName: String?): Valuation? {
        val url = SCRYFALL_NAMED.toHttpUrl().newBuilder()
            .addQueryParameter("fuzzy", name).build()
        val req = Request.Builder().url(url).header("User-Agent", "Lorebox/1.0").build()
        return runCatching {
            client.newCall(req).execute().use { r ->
                if (!r.isSuccessful) return null
                parseScryfallCard(r.body!!.string(), name)
            }
        }.getOrNull()
    }

    private fun ebayToken(): String? {
        val now = System.currentTimeMillis()
        token?.let { if (!isTokenExpired(now, tokenExpiry)) return it }
        val appId = keys.ebayAppId?.takeIf { it.isNotBlank() } ?: return null
        val certId = keys.ebayCertId?.takeIf { it.isNotBlank() } ?: return null
        val basic = Base64.getEncoder().encodeToString("$appId:$certId".toByteArray())
        val body = FormBody.Builder()
            .add("grant_type", "client_credentials").add("scope", BROWSE_SCOPE).build()
        val req = Request.Builder().url(EBAY_OAUTH)
            .header("Authorization", "Basic $basic")
            .header("Content-Type", "application/x-www-form-urlencoded")
            .post(body).build()
        return runCatching {
            client.newCall(req).execute().use { r ->
                if (!r.isSuccessful) return null
                val obj = Json.parseToJsonElement(r.body!!.string()).jsonObject
                val access = obj["access_token"]?.jsonPrimitive?.contentOrNull ?: return null
                val expiresIn = obj["expires_in"]?.jsonPrimitive?.intOrNull ?: 7200
                token = access
                tokenExpiry = computeExpiry(System.currentTimeMillis(), expiresIn)
                access
            }
        }.getOrNull()
    }

    private fun ebayBrowse(name: String, setName: String?, game: String?): Valuation? {
        val tok = ebayToken() ?: return null
        val query = buildEbayQuery(name, setName, game)
        val urlBuilder = EBAY_BROWSE.toHttpUrl().newBuilder()
            .addQueryParameter("q", query).addQueryParameter("limit", "100")
            .addQueryParameter("sort", "price")
            .addQueryParameter("filter", "buyingOptions:{FIXED_PRICE|AUCTION|AUCTION_WITH_BIN}")
        ebayCategory(game)?.let { urlBuilder.addQueryParameter("category_ids", it) }
        val req = Request.Builder().url(urlBuilder.build())
            .header("Authorization", "Bearer $tok")
            .header("X-EBAY-C-MARKETPLACE-ID", "EBAY_US")
            .header("X-EBAY-C-ENDUSERCTX", "contextualLocation=country=US").build()
        return runCatching {
            client.newCall(req).execute().use { r ->
                if (!r.isSuccessful) return null
                parseBrowseResponse(r.body!!.string(), query)
            }
        }.getOrNull()
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./gradlew :app:testDebugUnitTest --tests "*ValuationServiceOAuthTest"`
Expected: PASS.

- [ ] **Step 5: Create `IdentifyService.kt`**

```kotlin
package com.lorebox.android.data.identify

import com.lorebox.android.data.keys.KeyStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.contentOrNull
import org.json.JSONArray
import org.json.JSONObject
import java.util.Base64

class IdentifyService(
    private val keys: KeyStore,
    private val client: OkHttpClient = OkHttpClient(),
) {
    suspend fun identify(frontJpeg: ByteArray, backJpeg: ByteArray?): CardFields? =
        withContext(Dispatchers.IO) {
            val apiKey = keys.anthropicKey?.takeIf { it.isNotBlank() } ?: return@withContext null
            val content = JSONArray()
            for (img in listOfNotNull(frontJpeg, backJpeg)) {
                content.put(JSONObject().put("type", "image").put("source",
                    JSONObject().put("type", "base64").put("media_type", "image/jpeg")
                        .put("data", Base64.getEncoder().encodeToString(img))))
            }
            content.put(JSONObject().put("type", "text").put("text", VISION_PROMPT))
            val payload = JSONObject()
                .put("model", "claude-haiku-4-5-20251001")
                .put("max_tokens", 256)
                .put("messages", JSONArray().put(
                    JSONObject().put("role", "user").put("content", content)))
            val req = Request.Builder()
                .url("https://api.anthropic.com/v1/messages")
                .header("x-api-key", apiKey)
                .header("anthropic-version", "2023-06-01")
                .header("content-type", "application/json")
                .post(payload.toString().toRequestBody("application/json".toMediaType()))
                .build()
            runCatching {
                client.newCall(req).execute().use { r ->
                    if (!r.isSuccessful) return@withContext null
                    val obj = Json.parseToJsonElement(r.body!!.string()).jsonObject
                    val text = obj["content"]?.jsonArray?.firstOrNull()
                        ?.jsonObject?.get("text")?.jsonPrimitive?.contentOrNull ?: return@withContext null
                    parseIdentifyJson(text)
                }
            }.getOrNull()
        }
}
```

- [ ] **Step 6: Create `ImageStore.kt`**

```kotlin
package com.lorebox.android.data.image

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import java.io.ByteArrayOutputStream
import java.io.File

class ImageStore(private val context: Context) {
    private val dir: File get() = File(context.filesDir, "cards").apply { mkdirs() }

    fun save(bytes: ByteArray, prefix: String): String {
        val file = File(dir, "${prefix}_${System.currentTimeMillis()}.jpg")
        file.writeBytes(bytes)
        return file.absolutePath
    }

    fun downscaleJpeg(bytes: ByteArray): ByteArray {
        val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: return bytes
        val longest = maxOf(bmp.width, bmp.height)
        val scaled = if (longest > 1600) {
            val scale = 1600f / longest
            Bitmap.createScaledBitmap(bmp, (bmp.width * scale).toInt(), (bmp.height * scale).toInt(), true)
        } else bmp
        return ByteArrayOutputStream().use { out ->
            scaled.compress(Bitmap.CompressFormat.JPEG, 85, out); out.toByteArray()
        }
    }
}
```

- [ ] **Step 7: Build to verify everything compiles**

Run: `./gradlew :app:assembleDebug`
Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 8: Commit**

```bash
git add android/app/src/main/java/com/lorebox/android/data/identify/IdentifyService.kt android/app/src/main/java/com/lorebox/android/data/value/ValuationService.kt android/app/src/main/java/com/lorebox/android/data/image/ImageStore.kt android/app/src/test/java/com/lorebox/android/data/value/ValuationServiceOAuthTest.kt
git commit -m "feat(android): Anthropic/Scryfall/eBay services + image store"
```

---

## Task 9: CardRepository pipeline (TDD with fakes)

**Files:**
- Create: `data/CardRepository.kt`
- Modify: `LoreboxApp.kt` (expose a simple service container)
- Test: `android/app/src/test/java/com/lorebox/android/data/CardRepositoryTest.kt`

**Interfaces:**
- Consumes: `CardDao`, `IdentifyService`, `ValuationService`, `validateCard`, `CardInput`.
- Produces:
  - Interfaces `Identifier { suspend fun identify(front, back): CardFields? }` and
    `Valuator { suspend fun value(name, setName, game): Valuation? }` so services and fakes are interchangeable. `IdentifyService`/`ValuationService` implement them.
  - `data class ReviewDraft(fields: CardFields, valuation: Valuation?, frontPath: String, backPath: String?)`.
  - `class CardRepository(dao, identifier, valuator)`:
    - `suspend fun identifyAndValue(frontPath, backPath, frontJpeg, backJpeg): ReviewDraft`
    - `suspend fun saveCard(input: CardInput): Long` — validates, dedupe-merges (bump quantity) or inserts, records a `ValuationEntity` when value present.
    - `fun observeCollection(): Flow<List<CardEntity>>`, `suspend fun search`, `getById`, `delete`.

- [ ] **Step 1: Add `Identifier`/`Valuator` interfaces to their service files**

In `IdentifyService.kt` add above the class:
```kotlin
interface Identifier { suspend fun identify(frontJpeg: ByteArray, backJpeg: ByteArray?): CardFields? }
```
and change `class IdentifyService(...) : Identifier {`.

In `ValuationService.kt` add above the class:
```kotlin
interface Valuator { suspend fun value(name: String, setName: String?, game: String?): Valuation? }
```
and change `class ValuationService(...) : Valuator {`.

- [ ] **Step 2: Write the failing test**

```kotlin
package com.lorebox.android.data

import com.lorebox.android.data.db.CardEntity
import com.lorebox.android.data.identify.CardFields
import com.lorebox.android.data.identify.Identifier
import com.lorebox.android.data.value.Valuation
import com.lorebox.android.data.value.Valuator
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

private class FakeDao : com.lorebox.android.data.db.CardDao {
    val cards = mutableListOf<CardEntity>()
    var nextId = 1L
    val valuations = mutableListOf<com.lorebox.android.data.db.ValuationEntity>()
    override suspend fun insert(card: CardEntity): Long {
        val id = nextId++; cards.add(card.copy(id = id)); return id }
    override suspend fun insertValuation(v: com.lorebox.android.data.db.ValuationEntity): Long {
        valuations.add(v); return 1L }
    override suspend fun findDuplicateId(name: String?, setName: String?, cardNumber: String?, game: String?, foil: Int): Long? =
        cards.firstOrNull { it.name.equals(name, true) && it.setName == setName && it.cardNumber == cardNumber && it.game == game && it.foil == foil }?.id
    override suspend fun bumpQuantity(id: Long, by: Int, now: Long) {
        val i = cards.indexOfFirst { it.id == id }; cards[i] = cards[i].copy(quantity = cards[i].quantity + by) }
    override fun observeAll(): Flow<List<CardEntity>> = flowOf(cards)
    override suspend fun search(term: String): List<CardEntity> = cards.filter { it.name.contains(term, true) }
    override suspend fun getById(id: Long): CardEntity? = cards.firstOrNull { it.id == id }
    override suspend fun delete(id: Long) { cards.removeAll { it.id == id } }
    override suspend fun valuationsFor(cardId: Long) = valuations.filter { it.cardId == cardId }
}
private class FakeIdentifier(val f: CardFields?) : Identifier {
    override suspend fun identify(frontJpeg: ByteArray, backJpeg: ByteArray?) = f
}
private class FakeValuator(val v: Valuation?) : Valuator {
    override suspend fun value(name: String, setName: String?, game: String?) = v
}

class CardRepositoryTest {
    @Test fun identifyAndValuePopulatesDraft() = runTest {
        val repo = CardRepository(FakeDao(),
            FakeIdentifier(CardFields(name = "Black Lotus", game = "Magic: The Gathering")),
            FakeValuator(Valuation("Scryfall (LEA)", 9999.0, 9999.0, 9999.0, 1, "Black Lotus")))
        val draft = repo.identifyAndValue("/front.jpg", null, ByteArray(1), null)
        assertEquals("Black Lotus", draft.fields.name)
        assertEquals(9999.0, draft.valuation!!.value, 0.001)
    }

    @Test fun saveInsertsThenMergesDuplicate() = runTest {
        val dao = FakeDao()
        val repo = CardRepository(dao, FakeIdentifier(null), FakeValuator(null))
        val input = com.lorebox.android.data.db.CardInput(
            name = "Black Lotus", game = "Magic: The Gathering", estimatedValue = 9999.0)
        val id1 = repo.saveCard(input)
        val id2 = repo.saveCard(input)
        assertEquals(id1, id2)                 // merged
        assertEquals(1, dao.cards.size)
        assertEquals(2, dao.cards.first().quantity)
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `./gradlew :app:testDebugUnitTest --tests "*CardRepositoryTest"`
Expected: FAIL (unresolved `CardRepository` / `ReviewDraft`).

- [ ] **Step 4: Create `CardRepository.kt`**

```kotlin
package com.lorebox.android.data

import com.lorebox.android.data.db.CardDao
import com.lorebox.android.data.db.CardEntity
import com.lorebox.android.data.db.CardInput
import com.lorebox.android.data.db.ValuationEntity
import com.lorebox.android.data.db.validateCard
import com.lorebox.android.data.identify.CardFields
import com.lorebox.android.data.identify.Identifier
import com.lorebox.android.data.value.Valuation
import com.lorebox.android.data.value.Valuator
import kotlinx.coroutines.flow.Flow

data class ReviewDraft(
    val fields: CardFields,
    val valuation: Valuation?,
    val frontPath: String,
    val backPath: String?,
)

class CardRepository(
    private val dao: CardDao,
    private val identifier: Identifier,
    private val valuator: Valuator,
) {
    suspend fun identifyAndValue(
        frontPath: String, backPath: String?, frontJpeg: ByteArray, backJpeg: ByteArray?,
    ): ReviewDraft {
        val fields = identifier.identify(frontJpeg, backJpeg) ?: CardFields()
        val valuation = fields.name?.let { valuator.value(it, fields.setName, fields.game) }
        return ReviewDraft(fields, valuation, frontPath, backPath)
    }

    suspend fun saveCard(input: CardInput): Long {
        val v = validateCard(input)
        val dupId = dao.findDuplicateId(v.name, v.setName, v.cardNumber, v.game, v.foil)
        val id = if (dupId != null) {
            dao.bumpQuantity(dupId, v.quantity); dupId
        } else {
            dao.insert(CardEntity(
                name = v.name, setName = v.setName, cardNumber = v.cardNumber, rarity = v.rarity,
                game = v.game, year = v.year, language = v.language, foil = v.foil,
                frontScanPath = v.frontScanPath, backScanPath = v.backScanPath,
                conditionGrade = v.conditionGrade, conditionScore = v.conditionScore,
                defectsJson = v.defectsJson, estimatedValue = v.estimatedValue,
                purchasePrice = v.purchasePrice, purchaseDate = v.purchaseDate,
                notes = v.notes, quantity = v.quantity,
            ))
        }
        if (v.estimatedValue > 0) {
            dao.insertValuation(ValuationEntity(cardId = id, source = "estimate", value = v.estimatedValue))
        }
        return id
    }

    fun observeCollection(): Flow<List<CardEntity>> = dao.observeAll()
    suspend fun search(term: String) = dao.search(term)
    suspend fun getById(id: Long) = dao.getById(id)
    suspend fun delete(id: Long) = dao.delete(id)
}
```

- [ ] **Step 5: Wire a service container in `LoreboxApp.kt`**

```kotlin
package com.lorebox.android

import android.app.Application
import com.lorebox.android.data.CardRepository
import com.lorebox.android.data.db.LoreboxDatabase
import com.lorebox.android.data.identify.IdentifyService
import com.lorebox.android.data.image.ImageStore
import com.lorebox.android.data.keys.KeyStore
import com.lorebox.android.data.value.ValuationService

class LoreboxApp : Application() {
    lateinit var keyStore: KeyStore; private set
    lateinit var imageStore: ImageStore; private set
    lateinit var repository: CardRepository; private set

    override fun onCreate() {
        super.onCreate()
        keyStore = KeyStore(this)
        imageStore = ImageStore(this)
        val db = LoreboxDatabase.get(this)
        repository = CardRepository(
            db.cardDao(), IdentifyService(keyStore), ValuationService(keyStore))
    }
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `./gradlew :app:testDebugUnitTest --tests "*CardRepositoryTest"`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add android/app/src/main/java/com/lorebox/android/data/CardRepository.kt android/app/src/main/java/com/lorebox/android/LoreboxApp.kt android/app/src/main/java/com/lorebox/android/data/identify/IdentifyService.kt android/app/src/main/java/com/lorebox/android/data/value/ValuationService.kt android/app/src/test/java/com/lorebox/android/data/CardRepositoryTest.kt
git commit -m "feat(android): CardRepository identify->value->save pipeline"
```

---

## Task 10: Navigation + Collection & Detail screens

**Files:**
- Create: `ui/nav/LoreboxNav.kt`, `ui/collection/CollectionScreen.kt`, `ui/detail/CardDetailScreen.kt`
- Modify: `MainActivity.kt` (host the nav graph)

**Interfaces:**
- Consumes: `LoreboxApp.repository`.
- Produces: routes `collection`, `capture`, `review`, `detail/{id}`, `settings`, `pair`. A `CollectionViewModel` exposing `StateFlow<List<CardEntity>>` and a search query; `CardDetailViewModel` loading one card and supporting delete.

- [ ] **Step 1: Create `CollectionViewModel` + `CollectionScreen.kt`**

```kotlin
package com.lorebox.android.ui.collection

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lorebox.android.data.CardRepository
import com.lorebox.android.data.db.CardEntity
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

class CollectionViewModel(private val repo: CardRepository) : ViewModel() {
    private val query = MutableStateFlow("")
    val cards: StateFlow<List<CardEntity>> = query
        .flatMapLatest { q ->
            if (q.isBlank()) repo.observeCollection()
            else flow { emit(repo.search(q)) }
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
    fun onQuery(q: String) { query.value = q }
}
```

```kotlin
package com.lorebox.android.ui.collection

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.lorebox.android.data.db.CardEntity

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CollectionScreen(
    vm: CollectionViewModel,
    onAdd: () -> Unit,
    onOpen: (Long) -> Unit,
    onSettings: () -> Unit,
) {
    val cards by vm.cards.collectAsState()
    var q by remember { mutableStateOf("") }
    Scaffold(
        topBar = { TopAppBar(title = { Text("LoreBox") }, actions = {
            TextButton(onClick = onSettings) { Text("Settings") } }) },
        floatingActionButton = { FloatingActionButton(onClick = onAdd) {
            Icon(Icons.Default.Add, contentDescription = "Add card") } },
    ) { pad ->
        Column(Modifier.padding(pad)) {
            OutlinedTextField(value = q, onValueChange = { q = it; vm.onQuery(it) },
                label = { Text("Search") }, modifier = Modifier.fillMaxWidth().padding(8.dp))
            LazyColumn { items(cards) { c -> CardRow(c) { onOpen(c.id) } } }
        }
    }
}

@Composable
private fun CardRow(card: CardEntity, onClick: () -> Unit) {
    ListItem(
        headlineContent = { Text(card.name) },
        supportingContent = { Text(listOfNotNull(card.game, card.setName).joinToString(" · ")) },
        trailingContent = { Text("$%.2f".format(card.estimatedValue)) },
        modifier = Modifier.clickable(onClick = onClick).also { },
    )
    HorizontalDivider()
}
```
(Add `import androidx.compose.foundation.clickable`.)

- [ ] **Step 2: Create `CardDetailViewModel` + `CardDetailScreen.kt`**

```kotlin
package com.lorebox.android.ui.detail

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lorebox.android.data.CardRepository
import com.lorebox.android.data.db.CardEntity
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class CardDetailViewModel(private val repo: CardRepository, private val id: Long) : ViewModel() {
    private val _card = MutableStateFlow<CardEntity?>(null)
    val card: StateFlow<CardEntity?> = _card
    init { viewModelScope.launch { _card.value = repo.getById(id) } }
    fun delete(onDone: () -> Unit) = viewModelScope.launch { repo.delete(id); onDone() }
}
```

```kotlin
package com.lorebox.android.ui.detail

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CardDetailScreen(vm: CardDetailViewModel, onBack: () -> Unit) {
    val card by vm.card.collectAsState()
    Scaffold(topBar = { TopAppBar(title = { Text(card?.name ?: "Card") },
        navigationIcon = { TextButton(onClick = onBack) { Text("Back") } },
        actions = { TextButton(onClick = { vm.delete(onBack) }) { Text("Delete") } }) }) { pad ->
        card?.let { c ->
            Column(Modifier.padding(pad).padding(16.dp)) {
                Text("Set: ${c.setName ?: "—"}")
                Text("Game: ${c.game ?: "—"}")
                Text("Number: ${c.cardNumber ?: "—"}")
                Text("Rarity: ${c.rarity ?: "—"}")
                Text("Year: ${c.year ?: "—"}")
                Text("Quantity: ${c.quantity}")
                Text("Estimated value: $%.2f".format(c.estimatedValue))
            }
        }
    }
}
```

- [ ] **Step 3: Create `LoreboxNav.kt`**

```kotlin
package com.lorebox.android.ui.nav

import androidx.compose.runtime.Composable
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.lorebox.android.LoreboxApp
import com.lorebox.android.ui.collection.CollectionScreen
import com.lorebox.android.ui.collection.CollectionViewModel
import com.lorebox.android.ui.detail.CardDetailScreen
import com.lorebox.android.ui.detail.CardDetailViewModel
import androidx.compose.ui.platform.LocalContext

@Composable
fun LoreboxNav() {
    val nav = rememberNavController()
    val app = LocalContext.current.applicationContext as LoreboxApp
    NavHost(navController = nav, startDestination = "collection") {
        composable("collection") {
            CollectionScreen(
                vm = CollectionViewModel(app.repository),
                onAdd = { nav.navigate("capture") },
                onOpen = { id -> nav.navigate("detail/$id") },
                onSettings = { nav.navigate("settings") },
            )
        }
        composable("detail/{id}") { entry ->
            val id = entry.arguments?.getString("id")?.toLongOrNull() ?: return@composable
            CardDetailScreen(CardDetailViewModel(app.repository, id), onBack = { nav.popBackStack() })
        }
        // capture / review / settings / pair added in later tasks
    }
}
```

- [ ] **Step 4: Update `MainActivity.kt` to host the nav graph**

```kotlin
package com.lorebox.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.lorebox.android.ui.nav.LoreboxNav
import com.lorebox.android.ui.theme.LoreboxTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { LoreboxTheme { LoreboxNav() } }
    }
}
```

- [ ] **Step 5: Build & install to verify the list renders**

Run: `./gradlew :app:installDebug` then launch the app.
Expected: empty collection list with a Search field, an Add FAB, and a Settings action. Tapping a card (once data exists) opens detail.

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/java/com/lorebox/android/ui/nav/ android/app/src/main/java/com/lorebox/android/ui/collection/ android/app/src/main/java/com/lorebox/android/ui/detail/ android/app/src/main/java/com/lorebox/android/MainActivity.kt
git commit -m "feat(android): navigation, collection list, card detail"
```

---

## Task 11: Camera capture screen (CameraX)

**Files:**
- Create: `ui/capture/CaptureScreen.kt` (+ `CaptureViewModel`)
- Modify: `ui/nav/LoreboxNav.kt` (add `capture` route; pass captured paths to review)

**Interfaces:**
- Consumes: `LoreboxApp.imageStore`.
- Produces: `CaptureScreen` that requests camera permission, shows a CameraX preview, captures front then optional back, downscales + saves JPEGs via `ImageStore`, and calls `onCaptured(frontPath, backPath?)`. A holder `object CaptureBuffer { var frontPath; var backPath; var frontJpeg; var backJpeg }` to hand bytes to the review step without serializing through nav args.

- [ ] **Step 1: Create `CaptureBuffer` + `CaptureScreen.kt`**

```kotlin
package com.lorebox.android.ui.capture

object CaptureBuffer {
    var frontPath: String? = null
    var backPath: String? = null
    var frontJpeg: ByteArray? = null
    var backJpeg: ByteArray? = null
    fun clear() { frontPath = null; backPath = null; frontJpeg = null; backJpeg = null }
}
```

```kotlin
package com.lorebox.android.ui.capture

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.lorebox.android.LoreboxApp
import java.io.ByteArrayOutputStream
import java.util.concurrent.Executor

@Composable
fun CaptureScreen(onCaptured: (String, String?) -> Unit, onCancel: () -> Unit) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val app = context.applicationContext as LoreboxApp
    var hasPermission by remember { mutableStateOf(false) }
    var captureFront by remember { mutableStateOf(true) }
    val imageCapture = remember { ImageCapture.Builder().build() }

    val permLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()) { hasPermission = it }
    LaunchedEffect(Unit) {
        hasPermission = ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
            android.content.pm.PackageManager.PERMISSION_GRANTED
        if (!hasPermission) permLauncher.launch(Manifest.permission.CAMERA)
    }

    if (!hasPermission) {
        Column(Modifier.fillMaxSize().padding(24.dp)) {
            Text("Camera permission is required to capture cards.")
            Button(onClick = { permLauncher.launch(Manifest.permission.CAMERA) }) { Text("Grant") }
            TextButton(onClick = onCancel) { Text("Cancel") }
        }
        return
    }

    Box(Modifier.fillMaxSize()) {
        AndroidView(factory = { ctx ->
            val previewView = PreviewView(ctx)
            val providerFuture = ProcessCameraProvider.getInstance(ctx)
            providerFuture.addListener({
                val provider = providerFuture.get()
                val preview = Preview.Builder().build().also { it.setSurfaceProvider(previewView.surfaceProvider) }
                provider.unbindAll()
                provider.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, imageCapture)
            }, ContextCompat.getMainExecutor(ctx))
            previewView
        }, modifier = Modifier.fillMaxSize())

        Column(Modifier.align(androidx.compose.ui.Alignment.BottomCenter).padding(24.dp)) {
            Text(if (captureFront) "Capture FRONT" else "Capture BACK (optional)")
            Row {
                Button(onClick = {
                    takePhoto(context, imageCapture, ContextCompat.getMainExecutor(context)) { bytes ->
                        val scaled = app.imageStore.downscaleJpeg(bytes)
                        if (captureFront) {
                            CaptureBuffer.frontJpeg = scaled
                            CaptureBuffer.frontPath = app.imageStore.save(scaled, "front")
                            captureFront = false
                        } else {
                            CaptureBuffer.backJpeg = scaled
                            CaptureBuffer.backPath = app.imageStore.save(scaled, "back")
                            onCaptured(CaptureBuffer.frontPath!!, CaptureBuffer.backPath)
                        }
                    }
                }) { Text("Capture") }
                if (!captureFront) {
                    TextButton(onClick = { onCaptured(CaptureBuffer.frontPath!!, null) }) { Text("Skip back") }
                }
            }
        }
    }
}

private fun takePhoto(
    context: android.content.Context, imageCapture: ImageCapture,
    executor: Executor, onBytes: (ByteArray) -> Unit,
) {
    imageCapture.takePicture(executor, object : ImageCapture.OnImageCapturedCallback() {
        override fun onCaptureSuccess(image: androidx.camera.core.ImageProxy) {
            val buffer = image.planes[0].buffer
            val bytes = ByteArray(buffer.remaining()).also { buffer.get(it) }
            image.close(); onBytes(bytes)
        }
        override fun onError(exc: ImageCaptureException) { image_error(exc) }
    })
}
private fun image_error(exc: ImageCaptureException) { exc.printStackTrace() }
```

- [ ] **Step 2: Add the `capture` route in `LoreboxNav.kt`**

```kotlin
composable("capture") {
    com.lorebox.android.ui.capture.CaptureScreen(
        onCaptured = { _, _ -> nav.navigate("review") },
        onCancel = { nav.popBackStack() },
    )
}
```

- [ ] **Step 3: Build & install; manually verify capture**

Run: `./gradlew :app:installDebug`
Expected: tapping the Add FAB opens the camera; "Capture FRONT" → "Capture BACK" → navigates onward. (Review screen wired in Task 12.)

- [ ] **Step 4: Commit**

```bash
git add android/app/src/main/java/com/lorebox/android/ui/capture/ android/app/src/main/java/com/lorebox/android/ui/nav/LoreboxNav.kt
git commit -m "feat(android): CameraX capture (front + optional back)"
```

---

## Task 12: Review screen (identify + value + save)

**Files:**
- Create: `ui/review/ReviewScreen.kt` (+ `ReviewViewModel`)
- Modify: `ui/nav/LoreboxNav.kt` (add `review` route)

**Interfaces:**
- Consumes: `LoreboxApp.repository`, `CaptureBuffer`, `CardInput`.
- Produces: `ReviewViewModel` that on init runs `repository.identifyAndValue(...)` from `CaptureBuffer`, exposes an editable `StateFlow<ReviewUiState>` (all card fields + value + loading/error), and a `save()` that builds a `CardInput` (including `frontScanPath`/`backScanPath` and the fetched `estimatedValue`) and calls `repository.saveCard`.

- [ ] **Step 1: Create `ReviewViewModel`**

```kotlin
package com.lorebox.android.ui.review

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lorebox.android.data.CardRepository
import com.lorebox.android.data.db.CardInput
import com.lorebox.android.ui.capture.CaptureBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

data class ReviewUiState(
    val loading: Boolean = true,
    val name: String = "", val setName: String = "", val cardNumber: String = "",
    val game: String = "", val year: String = "", val rarity: String = "",
    val estimatedValue: Double = 0.0, val valueSource: String = "",
    val error: String? = null,
)

class ReviewViewModel(private val repo: CardRepository) : ViewModel() {
    private val _state = MutableStateFlow(ReviewUiState())
    val state: StateFlow<ReviewUiState> = _state

    init {
        viewModelScope.launch {
            val front = CaptureBuffer.frontJpeg
            if (front == null) { _state.value = ReviewUiState(loading = false, error = "No capture"); return@launch }
            val draft = repo.identifyAndValue(
                CaptureBuffer.frontPath ?: "", CaptureBuffer.backPath, front, CaptureBuffer.backJpeg)
            _state.value = ReviewUiState(
                loading = false,
                name = draft.fields.name ?: "", setName = draft.fields.setName ?: "",
                cardNumber = draft.fields.cardNumber ?: "", game = draft.fields.game ?: "",
                year = draft.fields.year?.toString() ?: "", rarity = draft.fields.rarity ?: "",
                estimatedValue = draft.valuation?.value ?: 0.0,
                valueSource = draft.valuation?.source ?: "No data",
            )
        }
    }

    fun update(transform: (ReviewUiState) -> ReviewUiState) { _state.value = transform(_state.value) }

    fun save(onDone: () -> Unit) {
        viewModelScope.launch {
            val s = _state.value
            repo.saveCard(CardInput(
                name = s.name, setName = s.setName.ifBlank { null },
                cardNumber = s.cardNumber.ifBlank { null }, game = s.game.ifBlank { null },
                rarity = s.rarity.ifBlank { null }, year = s.year.toIntOrNull(),
                estimatedValue = s.estimatedValue,
                frontScanPath = CaptureBuffer.frontPath, backScanPath = CaptureBuffer.backPath,
            ))
            CaptureBuffer.clear(); onDone()
        }
    }
}
```

- [ ] **Step 2: Create `ReviewScreen.kt`**

```kotlin
package com.lorebox.android.ui.review

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReviewScreen(vm: ReviewViewModel, onSaved: () -> Unit, onCancel: () -> Unit) {
    val s by vm.state.collectAsState()
    Scaffold(topBar = { TopAppBar(title = { Text("Review card") },
        navigationIcon = { TextButton(onClick = onCancel) { Text("Cancel") } }) }) { pad ->
        if (s.loading) { Box(Modifier.fillMaxSize().padding(pad)) { CircularProgressIndicator(Modifier.align(androidx.compose.ui.Alignment.Center)) }; return@Scaffold }
        Column(Modifier.padding(pad).padding(16.dp).verticalScroll(rememberScrollState())) {
            s.error?.let { Text("Error: $it") }
            field("Name", s.name) { v -> vm.update { it.copy(name = v) } }
            field("Set", s.setName) { v -> vm.update { it.copy(setName = v) } }
            field("Number", s.cardNumber) { v -> vm.update { it.copy(cardNumber = v) } }
            field("Game", s.game) { v -> vm.update { it.copy(game = v) } }
            field("Year", s.year) { v -> vm.update { it.copy(year = v) } }
            field("Rarity", s.rarity) { v -> vm.update { it.copy(rarity = v) } }
            Spacer(Modifier.height(8.dp))
            Text("Estimated value: $%.2f  (%s)".format(s.estimatedValue, s.valueSource))
            Spacer(Modifier.height(16.dp))
            Button(onClick = { vm.save(onSaved) }, enabled = s.name.isNotBlank()) { Text("Save to collection") }
        }
    }
}

@Composable
private fun field(label: String, value: String, onChange: (String) -> Unit) {
    OutlinedTextField(value = value, onValueChange = onChange, label = { Text(label) },
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp))
}
```

- [ ] **Step 3: Wire the `review` route and fix `capture` to navigate to it**

In `LoreboxNav.kt`:
```kotlin
composable("review") {
    com.lorebox.android.ui.review.ReviewScreen(
        vm = com.lorebox.android.ui.review.ReviewViewModel(app.repository),
        onSaved = { nav.popBackStack("collection", inclusive = false) },
        onCancel = { nav.popBackStack("collection", inclusive = false) },
    )
}
```

- [ ] **Step 4: Build & install; manual end-to-end check**

Run: `./gradlew :app:installDebug`
Expected (with an Anthropic key set, Task 13): capture a Magic card → Review shows identified fields + a Scryfall value → Save → it appears in the collection list. Without a key: fields blank but manually editable, save still works.

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/java/com/lorebox/android/ui/review/ android/app/src/main/java/com/lorebox/android/ui/nav/LoreboxNav.kt
git commit -m "feat(android): review screen — identify, value, edit, save"
```

---

## Task 13: Settings + QR pairing (ZXing) + manual key entry

**Files:**
- Create: `ui/settings/SettingsScreen.kt` (+ `SettingsViewModel`), `ui/pair/PairScreen.kt`
- Modify: `ui/nav/LoreboxNav.kt` (add `settings`, `pair` routes)

**Interfaces:**
- Consumes: `LoreboxApp.keyStore`, `parseProvisioning`, ZXing `ScanContract`.
- Produces: a Settings screen showing whether each key is set, manual entry fields, an app-lock toggle, and a "Pair with PC (scan QR)" button that launches ZXing; on a successful scan, `keyStore.importFrom(parseProvisioning(result))`.

- [ ] **Step 1: Create `SettingsViewModel` + `SettingsScreen.kt`**

```kotlin
package com.lorebox.android.ui.settings

import androidx.lifecycle.ViewModel
import com.lorebox.android.data.keys.KeyStore

class SettingsViewModel(private val keys: KeyStore) : ViewModel() {
    fun anthropic() = keys.anthropicKey ?: ""
    fun ebayApp() = keys.ebayAppId ?: ""
    fun ebayCert() = keys.ebayCertId ?: ""
    fun lock() = keys.appLockEnabled
    fun saveAnthropic(v: String) { keys.anthropicKey = v.ifBlank { null } }
    fun saveEbayApp(v: String) { keys.ebayAppId = v.ifBlank { null } }
    fun saveEbayCert(v: String) { keys.ebayCertId = v.ifBlank { null } }
    fun setLock(v: Boolean) { keys.appLockEnabled = v }
}
```

```kotlin
package com.lorebox.android.ui.settings

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(vm: SettingsViewModel, onBack: () -> Unit, onPair: () -> Unit) {
    var anthropic by remember { mutableStateOf(vm.anthropic()) }
    var ebayApp by remember { mutableStateOf(vm.ebayApp()) }
    var ebayCert by remember { mutableStateOf(vm.ebayCert()) }
    var lock by remember { mutableStateOf(vm.lock()) }
    Scaffold(topBar = { TopAppBar(title = { Text("Settings") },
        navigationIcon = { TextButton(onClick = onBack) { Text("Back") } }) }) { pad ->
        Column(Modifier.padding(pad).padding(16.dp)) {
            Button(onClick = onPair, modifier = Modifier.fillMaxWidth()) { Text("Pair with PC (scan QR)") }
            Spacer(Modifier.height(16.dp))
            OutlinedTextField(anthropic, { anthropic = it; vm.saveAnthropic(it) },
                label = { Text("Anthropic API key") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(ebayApp, { ebayApp = it; vm.saveEbayApp(it) },
                label = { Text("eBay App ID") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(ebayCert, { ebayCert = it; vm.saveEbayCert(it) },
                label = { Text("eBay Cert ID") }, modifier = Modifier.fillMaxWidth())
            Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Switch(checked = lock, onCheckedChange = { lock = it; vm.setLock(it) })
                Text("Require biometric/PIN to open")
            }
        }
    }
}
```

- [ ] **Step 2: Add `settings` + `pair` routes and ZXing scan launcher in `LoreboxNav.kt`**

```kotlin
composable("settings") {
    com.lorebox.android.ui.settings.SettingsScreen(
        vm = com.lorebox.android.ui.settings.SettingsViewModel(app.keyStore),
        onBack = { nav.popBackStack() },
        onPair = { nav.navigate("pair") },
    )
}
composable("pair") {
    com.lorebox.android.ui.pair.PairScreen(
        keyStore = app.keyStore, onDone = { nav.popBackStack() })
}
```

- [ ] **Step 3: Create `PairScreen.kt` (ZXing offline scan)**

```kotlin
package com.lorebox.android.ui.pair

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import com.lorebox.android.data.keys.KeyStore
import com.lorebox.android.data.keys.parseProvisioning

@Composable
fun PairScreen(keyStore: KeyStore, onDone: () -> Unit) {
    var status by remember { mutableStateOf("Tap to scan the QR code shown in the desktop app's \"Pair phone\" dialog.") }
    val launcher = rememberLauncherForActivityResult(ScanContract()) { result ->
        val contents = result.contents
        if (contents == null) { status = "Scan cancelled." } else {
            val payload = parseProvisioning(contents)
            if (payload == null) status = "That QR code wasn't a valid LoreBox pairing code."
            else { keyStore.importFrom(payload); status = "Keys imported successfully."; onDone() }
        }
    }
    Column(Modifier.fillMaxSize().padding(24.dp)) {
        Text(status)
        Spacer(Modifier.height(16.dp))
        Button(onClick = {
            launcher.launch(ScanOptions().setOrientationLocked(false)
                .setPrompt("Scan LoreBox pairing QR").setBeepEnabled(false))
        }) { Text("Scan QR") }
        TextButton(onClick = onDone) { Text("Back") }
    }
}
```

- [ ] **Step 4: Build & install; verify Settings + manual key entry persist**

Run: `./gradlew :app:installDebug`
Expected: entering a key in Settings and re-opening the app shows it persisted (EncryptedSharedPreferences). The Pair button opens the ZXing scanner.

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/java/com/lorebox/android/ui/settings/ android/app/src/main/java/com/lorebox/android/ui/pair/ android/app/src/main/java/com/lorebox/android/ui/nav/LoreboxNav.kt
git commit -m "feat(android): settings, manual keys, QR pairing (ZXing)"
```

---

## Task 14: Optional biometric app-lock

**Files:**
- Create: `ui/lock/AppLock.kt`
- Modify: `MainActivity.kt`

**Interfaces:**
- Consumes: `LoreboxApp.keyStore`, AndroidX `BiometricPrompt`.
- Produces: `fun promptAppLock(activity: FragmentActivity, onSuccess, onFail)` and a gate in `MainActivity` that, when `keyStore.appLockEnabled`, shows a locked state until biometric/device-credential auth succeeds.

- [ ] **Step 1: Change `MainActivity` base class to `FragmentActivity`**

BiometricPrompt requires a `FragmentActivity`. In `MainActivity.kt` replace `ComponentActivity` with `androidx.fragment.app.FragmentActivity` (add `implementation("androidx.fragment:fragment-ktx:1.8.3")` to `app/build.gradle.kts` dependencies).

- [ ] **Step 2: Create `AppLock.kt`**

```kotlin
package com.lorebox.android.ui.lock

import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity

fun promptAppLock(activity: FragmentActivity, onSuccess: () -> Unit, onFail: () -> Unit) {
    val allowed = BiometricManager.Authenticators.BIOMETRIC_WEAK or
        BiometricManager.Authenticators.DEVICE_CREDENTIAL
    val can = BiometricManager.from(activity).canAuthenticate(allowed)
    if (can != BiometricManager.BIOMETRIC_SUCCESS) { onSuccess(); return } // no lock available → don't lock out
    val prompt = BiometricPrompt(activity, ContextCompat.getMainExecutor(activity),
        object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) = onSuccess()
            override fun onAuthenticationError(code: Int, msg: CharSequence) = onFail()
        })
    prompt.authenticate(BiometricPrompt.PromptInfo.Builder()
        .setTitle("Unlock LoreBox").setAllowedAuthenticators(allowed).build())
}
```

- [ ] **Step 3: Gate the UI in `MainActivity.kt`**

```kotlin
package com.lorebox.android

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.fragment.app.FragmentActivity
import com.lorebox.android.ui.lock.promptAppLock
import com.lorebox.android.ui.nav.LoreboxNav
import com.lorebox.android.ui.theme.LoreboxTheme

class MainActivity : FragmentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val keyStore = (application as LoreboxApp).keyStore
        setContent {
            LoreboxTheme {
                var unlocked by remember { mutableStateOf(!keyStore.appLockEnabled) }
                LaunchedEffect(Unit) {
                    if (keyStore.appLockEnabled) {
                        promptAppLock(this@MainActivity, onSuccess = { unlocked = true }, onFail = { finish() })
                    }
                }
                if (unlocked) LoreboxNav() else Surface { Text("Locked") }
            }
        }
    }
}
```

- [ ] **Step 4: Build & install; verify the lock**

Run: `./gradlew :app:installDebug`
Expected: with app-lock enabled in Settings, relaunching prompts for biometric/device PIN; on a device with no biometrics enrolled, the app opens normally (no lock-out).

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/java/com/lorebox/android/ui/lock/ android/app/src/main/java/com/lorebox/android/MainActivity.kt android/app/build.gradle.kts
git commit -m "feat(android): optional biometric app-lock"
```

---

## Task 15: Desktop "Pair phone" QR dialog

**Files:**
- Create: `ui/pair_dialog.py`
- Modify: `ui/main_window.py` (add a menu/button action to open the dialog)
- Modify: `ui/settings_dialog.py` only if keys are read from there (read keys from `core.config`)

**Interfaces:**
- Consumes: existing `core.config` (Anthropic/eBay keys), existing `qrcode` dependency, PyQt6.
- Produces: `class PairPhoneDialog(QDialog)` that builds the JSON payload
  `{"anthropicKey","ebayAppId","ebayCertId"}` from config and renders it as a QR
  via `qrcode`, displayed in a `QLabel`. A `MainWindow` action opens it.

- [ ] **Step 1: Inspect how desktop stores keys**

Run: open `core/config.py` and confirm the attribute/getter names for the Anthropic key, eBay App ID, and eBay Cert ID (e.g. `config.anthropic_api_key`). Use the real names found there in Step 2.

- [ ] **Step 2: Create `ui/pair_dialog.py`**

```python
"""Pair phone dialog — renders a QR code that provisions the Android app's keys.

The QR encodes a small JSON payload the LoreBox Android app scans on first run.
It is shown on the user's own PC and scanned by their own phone — keys never
transit a network. See docs/superpowers/specs/2026-06-22-lorebox-android-v1-design.md.
"""

import io
import json
import qrcode
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout

from core.config import config


class PairPhoneDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pair phone")
        layout = QVBoxLayout(self)

        info = QLabel(
            "Scan this code from the LoreBox Android app\n"
            "(Settings → Pair with PC) to copy your API keys to the phone.\n"
            "Keep this screen private — it contains your keys."
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        payload = json.dumps(self._payload())
        img = qrcode.make(payload)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        pix = QPixmap()
        pix.loadFromData(buf.getvalue(), "PNG")

        qr_label = QLabel()
        qr_label.setPixmap(pix)
        qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(qr_label)

    @staticmethod
    def _payload() -> dict:
        # NOTE: confirm these getter names against core/config.py in Step 1.
        return {
            "anthropicKey": config.get("ANTHROPIC_API_KEY", "") or "",
            "ebayAppId": config.get("EBAY_APP_ID", "") or "",
            "ebayCertId": config.get("EBAY_CERT_ID", "") or "",
        }
```

- [ ] **Step 3: Add a MainWindow action to open the dialog**

In `ui/main_window.py`, add (near other menu/toolbar actions):
```python
def _open_pair_dialog(self):
    from ui.pair_dialog import PairPhoneDialog
    PairPhoneDialog(self).exec()
```
and wire a menu item / button labelled "Pair phone…" to `self._open_pair_dialog`.

- [ ] **Step 4: Manually verify the QR renders**

Run: `python main.py`, open the new "Pair phone…" action.
Expected: a dialog shows a scannable QR. Verify the Android Pair screen (Task 13) imports the keys when scanning it.

- [ ] **Step 5: Commit**

```bash
git add ui/pair_dialog.py ui/main_window.py
git commit -m "feat(desktop): Pair phone QR dialog for Android key provisioning"
```

---

## Task 16: README + run docs for the Android app

**Files:**
- Create: `android/README.md`

**Interfaces:** none.

- [ ] **Step 1: Create `android/README.md`**

````markdown
# LoreBox Android

Standalone-capable companion app for LoreBox. Capture a card with the camera →
identify (Claude vision) → value (Scryfall / eBay) → save to a local collection.

## Build

```bash
cd android
./gradlew :app:assembleDebug      # or installDebug to a connected device
```

Requirements: JDK 17, Android SDK (compileSdk 35), a device/emulator on API 26+.

## Keys

- **Magic cards work with no keys** (Scryfall).
- For identify and non-Magic valuation, add keys in **Settings**, or **Pair with PC**:
  open the desktop app's "Pair phone…" dialog and scan the QR.

## Tests

```bash
./gradlew :app:testDebugUnitTest            # pure logic (validation, parsers, pipeline)
./gradlew :app:connectedDebugAndroidTest    # Room (needs a device/emulator)
```

## Scope

v1: capture, identify, value, local collection, QR key provisioning, optional app-lock.
Deferred: condition grading, live LAN sync, Epson scanner SDK, reports.
````

- [ ] **Step 2: Commit**

```bash
git add android/README.md
git commit -m "docs(android): build, keys, and test instructions"
```

---

## Self-Review

**Spec coverage:**
- Camera capture → Task 11. Identify (Claude vision, same prompt/model) → Tasks 4, 8, 12. Valuation (Scryfall + eBay, 0.85 discount) → Tasks 5, 6, 8. Local Room collection mirroring desktop schema → Tasks 2, 3. Duplicate merge → Tasks 3, 9. Settings/API keys (encrypted) → Tasks 7, 13. QR provisioning (phone scan + desktop dialog) → Tasks 13, 15. Optional biometric app-lock → Task 14. Privacy/offline QR (ZXing) → Global Constraints + Task 13. Branch + `/android` layout → Global Constraints + Task 1. Testing strategy → Tasks 2–9. README → Task 16. All spec sections map to tasks.
- Deferred items (grading, LAN sync, Epson, reports) are explicitly out of scope — no tasks, as intended.

**Placeholder scan:** No "TBD/TODO/implement later". The one note (Task 15 confirming `core/config.py` getter names) is an explicit inspection step with a concrete fallback, not a placeholder.

**Type consistency:** `CardInput`/`validateCard` (Task 2) used consistently in Tasks 9, 12. `CardFields` (Task 4) used in 8, 9, 12. `Valuation` (Task 5) used in 6, 8, 9, 12. `Identifier`/`Valuator` interfaces (Task 9) implemented by services (Task 8 classes, interface added in Task 9 Step 1). `ReviewDraft` (Task 9) used in 12. DAO method names (`findDuplicateId`, `bumpQuantity`, `observeAll`, `search`, `getById`, `delete`, `insertValuation`) consistent across Tasks 3, 9. `CaptureBuffer` fields consistent across Tasks 11, 12. `KeyStore` accessors consistent across Tasks 7, 13, 14. Provisioning payload keys (`anthropicKey`/`ebayAppId`/`ebayCertId`) match between Android (Task 7) and desktop (Task 15).
