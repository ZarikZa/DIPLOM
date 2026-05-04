package com.example.hhdiplom.api;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import com.example.hhdiplom.models.RefreshTokenRequest;
import com.example.hhdiplom.models.TokenResponse;
import com.example.hhdiplom.models.UserProfile;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import java.io.IOException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.ReentrantLock;

import okhttp3.Interceptor;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.ResponseBody;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

/**
 * Полная версия ApiClient:
 * - НЕ чистит токены при сетевых ошибках refresh (таймаут/нет связи)
 * - Во время загрузки (UploadGate.isUploading()) не делает refresh на 401
 * - НЕ ставит Content-Type вручную (важно для multipart)
 */
public class ApiClient {

    public static final String BASE_URL = "http://172.20.10.2:8001/";

    private static final String PREF_NAME = "auth_prefs";
    private static final String KEY_ACCESS_TOKEN = "access_token";
    private static final String KEY_REFRESH_TOKEN = "refresh_token";
    private static final String KEY_USER_ID = "user_id";
    private static final String KEY_USER_TYPE = "user_type";
    private static final String KEY_USERNAME = "username";
    private static final String KEY_EMAIL = "email";
    private static final String KEY_FIRST_NAME = "first_name";
    private static final String KEY_LAST_NAME = "last_name";
    private static final String KEY_PHONE = "phone";
    private static final String KEY_EMPLOYEE_ROLE = "employee_role";
    private static final String KEY_EMPLOYEE_ROLE_OVERRIDE = "employee_role_override";
    private static final String KEY_COMPANY_ID = "company_id";
    private static final String KEY_APPLICANT_ID = "applicant_id";

    private static Retrofit retrofit = null;
    private static com.example.hhdiplom.api.ApiService apiService = null;
    private static SharedPreferences sharedPreferences = null;

    // синхронизация refresh
    private static final ReentrantLock refreshLock = new ReentrantLock();
    private static volatile boolean isRefreshing = false;

    public static void init(Context context) {
        if (sharedPreferences == null) {
            sharedPreferences = context.getApplicationContext()
                    .getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE);
        }
    }

    public static com.example.hhdiplom.api.ApiService getApiService() {
        if (apiService == null) {
            retrofit = createRetrofit();
            apiService = retrofit.create(com.example.hhdiplom.api.ApiService.class);
        }
        return apiService;
    }

    public static String getEmployeeRoleOverride() {
        if (sharedPreferences == null) return "";
        return sharedPreferences.getString(KEY_EMPLOYEE_ROLE_OVERRIDE, "");
    }


    public static void saveUserInfo(UserProfile userProfile) {
        if (userProfile == null || sharedPreferences == null) return;

        SharedPreferences.Editor editor = sharedPreferences.edit();
        editor.putString(KEY_USERNAME, userProfile.getUsername());
        editor.putString(KEY_EMAIL, userProfile.getEmail());
        editor.putString(KEY_USER_TYPE, userProfile.getUserType());
        editor.putString(KEY_FIRST_NAME, userProfile.getFirstName());
        editor.putString(KEY_LAST_NAME, userProfile.getLastName());
        editor.putString(KEY_PHONE, userProfile.getPhone());
        editor.putString(KEY_EMPLOYEE_ROLE, userProfile.getEmployeeRole());

        if (userProfile.getCompanyId() != null) editor.putInt(KEY_COMPANY_ID, userProfile.getCompanyId());
        else editor.remove(KEY_COMPANY_ID);

        if (userProfile.getApplicantId() != null) editor.putInt(KEY_APPLICANT_ID, userProfile.getApplicantId());
        else editor.remove(KEY_APPLICANT_ID);

        editor.apply();
    }

    public static String getUsername() {
        if (sharedPreferences == null) return "";
        return sharedPreferences.getString(KEY_USERNAME, "");
    }

    public static String getUserEmail() {
        if (sharedPreferences == null) return "";
        return sharedPreferences.getString(KEY_EMAIL, "");
    }

    public static String getEmployeeRole() {
        if (sharedPreferences == null) return "";
        return sharedPreferences.getString(KEY_EMPLOYEE_ROLE, "");
    }

    public static void saveEmployeeRoleOverride(String employeeRole) {
        if (sharedPreferences == null) return;
        sharedPreferences.edit()
                .putString(KEY_EMPLOYEE_ROLE_OVERRIDE, employeeRole == null ? "" : employeeRole)
                .apply();
    }

    public static Integer getCompanyId() {
        if (sharedPreferences == null) return null;
        if (!sharedPreferences.contains(KEY_COMPANY_ID)) return null;
        return sharedPreferences.getInt(KEY_COMPANY_ID, 0);
    }

    public static Integer getApplicantId() {
        if (sharedPreferences == null) return null;
        if (!sharedPreferences.contains(KEY_APPLICANT_ID)) return null;
        return sharedPreferences.getInt(KEY_APPLICANT_ID, 0);
    }

    public static int getUserId() {
        if (sharedPreferences == null) return 0;
        return sharedPreferences.getInt(KEY_USER_ID, 0);
    }

    public static void saveTokens(String accessToken, String refreshToken, int userId, String userType) {
        if (sharedPreferences == null) {
            throw new IllegalStateException("ApiClient не инициализирован. Вызови ApiClient.init(context) сначала.");
        }

        SharedPreferences.Editor editor = sharedPreferences.edit();
        editor.putString(KEY_ACCESS_TOKEN, accessToken);
        editor.putString(KEY_REFRESH_TOKEN, refreshToken);
        editor.putInt(KEY_USER_ID, userId);
        editor.putString(KEY_USER_TYPE, userType);
        editor.apply();

        if (accessToken != null) {
            String preview = accessToken.length() > 20 ? accessToken.substring(0, 20) + "..." : accessToken;
            Log.d("ApiClient", "Tokens saved: access=" + preview);
        } else {
            Log.w("ApiClient", "Tokens saved WITHOUT access token (null)");
        }

        // пересобираем сервис (чтобы новый токен попал в интерсептор)
        apiService = null;
        retrofit = null;
        getApiService();
    }

    public static void clearTokens() {
        if (sharedPreferences == null) return;

        SharedPreferences.Editor editor = sharedPreferences.edit();
        editor.remove(KEY_ACCESS_TOKEN);
        editor.remove(KEY_REFRESH_TOKEN);
        editor.remove(KEY_USER_ID);
        editor.remove(KEY_USER_TYPE);
        editor.remove(KEY_USERNAME);
        editor.remove(KEY_EMAIL);
        editor.remove(KEY_FIRST_NAME);
        editor.remove(KEY_LAST_NAME);
        editor.remove(KEY_PHONE);
        editor.remove(KEY_EMPLOYEE_ROLE);
        editor.remove(KEY_EMPLOYEE_ROLE_OVERRIDE);
        editor.remove(KEY_COMPANY_ID);
        editor.remove(KEY_APPLICANT_ID);
        editor.apply();

        apiService = null;
        retrofit = null;
        Log.d("ApiClient", "Tokens cleared");
    }

    public static String getAccessToken() {
        if (sharedPreferences == null) return null;
        return sharedPreferences.getString(KEY_ACCESS_TOKEN, null);
    }

    public static String getRefreshToken() {
        if (sharedPreferences == null) return null;
        return sharedPreferences.getString(KEY_REFRESH_TOKEN, null);
    }

    public static String getUserType() {
        if (sharedPreferences == null) return "";
        return sharedPreferences.getString(KEY_USER_TYPE, "");
    }

    public static boolean isLoggedIn() {
        return getAccessToken() != null;
    }

    // ============ REFRESH TOKEN ============

    /**
     * refreshToken:
     * - НЕ чистит токены на сетевых ошибках (IOException/timeout/connect)
     * - чистит токены ТОЛЬКО если сервер явно отверг refresh (400/401)
     */
    public static boolean refreshToken() {
        String refreshToken = getRefreshToken();
        if (refreshToken == null) {
            Log.d("ApiClient", "No refresh token available");
            return false;
        }

        if (isRefreshing) {
            Log.d("ApiClient", "Already refreshing, skip");
            return true;
        }

        refreshLock.lock();
        isRefreshing = true;

        try {
            Log.d("ApiClient", "Attempting to refresh token");

            OkHttpClient tempClient = new OkHttpClient.Builder()
                    .connectTimeout(30, TimeUnit.SECONDS)
                    .readTimeout(120, TimeUnit.SECONDS)
                    .writeTimeout(120, TimeUnit.SECONDS)
                    .retryOnConnectionFailure(true)
                    .addInterceptor(new AuthInterceptor())           // Accept + Authorization (если надо)
                    .addInterceptor(new ForceUtf8JsonInterceptor()) // твой интерсептор
                    .build();

            Retrofit tempRetrofit = new Retrofit.Builder()
                    .baseUrl(BASE_URL)
                    .client(tempClient)
                    .addConverterFactory(GsonConverterFactory.create())
                    .build();

            com.example.hhdiplom.api.ApiService tempService = tempRetrofit.create(com.example.hhdiplom.api.ApiService.class);

            retrofit2.Response<TokenResponse> response =
                    tempService.refreshToken(new RefreshTokenRequest(refreshToken)).execute();

            if (response.isSuccessful() && response.body() != null) {
                TokenResponse tr = response.body();
                saveTokens(tr.getAccessToken(), tr.getRefreshToken(), tr.getUserId(), tr.getUserType());
                Log.d("ApiClient", "Token refreshed successfully");
                return true;
            }

            int code = response.code();
            Log.w("ApiClient", "Refresh failed: code=" + code);

            // ✅ только невалидный refresh -> logout
            if (code == 400 || code == 401) {
                Log.w("ApiClient", "Refresh rejected by server -> clearing tokens");
                clearTokens();
            } else {
                Log.w("ApiClient", "Refresh failed (tokens kept)");
            }
            return false;

        } catch (IOException net) {
            // ✅ сеть/таймаут/usb-тетеринг -> токены НЕ чистим
            Log.e("ApiClient", "Refresh network error (tokens kept): " + net.getMessage(), net);
            return false;

        } catch (Exception e) {
            Log.e("ApiClient", "Refresh error: " + e.getMessage(), e);
            return false;

        } finally {
            isRefreshing = false;
            refreshLock.unlock();
        }
    }


    private static Retrofit createRetrofit() {

        Gson gson = new GsonBuilder()
                .setLenient()
                .setDateFormat("yyyy-MM-dd'T'HH:mm:ss")
                .create();

        OkHttpClient client = new OkHttpClient.Builder()
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(5, TimeUnit.MINUTES)
                .writeTimeout(5, TimeUnit.MINUTES)
                .retryOnConnectionFailure(true)
                .addInterceptor(new BlockCmVideosDuringUploadInterceptor())

                // если у тебя есть EventListener:
                .eventListenerFactory(call -> new NetEventLogger())
                .addNetworkInterceptor(new UploadWireLogger())

                // твои логгеры (они не читают body — можно оставлять)
                .addInterceptor(new RequestDebugInterceptor())
                .addInterceptor(new RequestMetaLogger())

                // auth / errors / encoding
                .addInterceptor(new AuthInterceptor())
                .addInterceptor(new ErrorInterceptor())
                .addInterceptor(new ForceUtf8JsonInterceptor())
                .build();

        return new Retrofit.Builder()
                .baseUrl(BASE_URL)
                .client(client)
                .addConverterFactory(GsonConverterFactory.create(gson))
                .build();
    }

    // ============ HELPERS ============

    public static boolean checkAndRefreshToken() {
        // вызываться может TokenManager-ом
        return isLoggedIn() && refreshToken();
    }

    // ============ INTERCEPTORS ============

    /**
     * Добавляет Authorization (Bearer) и Accept.
     * ВАЖНО: НЕ ставим Content-Type вручную, иначе ломается multipart.
     */
    static class AuthInterceptor implements Interceptor {
        @Override
        public okhttp3.Response intercept(Chain chain) throws IOException {
            Request original = chain.request();
            String url = original.url().toString();

            // не добавляем токен на auth endpoints
            if (url.contains("/api/token/")
                    || url.contains("/api/token/refresh/")
                    || url.contains("/api/user/register_applicant/")
                    || url.contains("/api/auth/login/")
                    || url.contains("/api/password/reset/")
                    || url.contains("/api/auth/password-reset/")) {
                return chain.proceed(original);
            }

            String accessToken = getAccessToken();

            Request.Builder b = original.newBuilder();
            b.header("Accept", "application/json");

            if (accessToken != null && !accessToken.trim().isEmpty()) {
                b.header("Authorization", "Bearer " + accessToken);
            }

            return chain.proceed(b.build());
        }
    }

    /**
     * Обработка 401:
     * - если идёт upload -> НЕ делаем refresh и НЕ чистим токены, просто отдаём 401 наверх
     * - иначе пробуем refresh и повторяем запрос
     * - если refresh не удался -> возвращаем 401 (НЕ бросаем IOException, НЕ clearTokens тут)
     */
    static class ErrorInterceptor implements Interceptor {
        @Override
        public okhttp3.Response intercept(Chain chain) throws IOException {
            Request request = chain.request();
            String url = request.url().toString();

            // пропускаем auth запросы
            if (url.contains("/api/token/")
                    || url.contains("/api/token/refresh/")
                    || url.contains("/api/user/register_applicant/")
                    || url.contains("/api/auth/login/")
                    || url.contains("/api/password/reset/")
                    || url.contains("/api/auth/password-reset/")) {
                return chain.proceed(request);
            }

            okhttp3.Response response = chain.proceed(request);

            if (response.code() == 401) {

                // ✅ во время загрузки не трогаем refresh вообще
                if (UploadGate.isUploading()) {
                    Log.w("ApiClient", "401 during upload -> skip refresh, keep tokens");
                    return response;
                }

                Log.d("ApiClient", "Received 401, attempting token refresh");

                // закрываем старый ответ
                response.close();

                boolean refreshed = refreshToken();
                if (refreshed) {
                    String newAccessToken = getAccessToken();
                    if (newAccessToken != null && !newAccessToken.trim().isEmpty()) {
                        Request newRequest = request.newBuilder()
                                .header("Authorization", "Bearer " + newAccessToken)
                                .build();
                        return chain.proceed(newRequest);
                    }
                }

                // ✅ refresh не удался: возвращаем 401 как есть (без logout)
                Log.w("ApiClient", "Refresh failed or no token, returning 401");
                return chain.proceed(request);
            }

            return response;
        }
    }

    /**
     * Если у тебя есть ForceUtf8JsonInterceptor — оставь свой.
     * Ниже заглушка на случай, если нужно компилировать.
     * УДАЛИ, если у тебя он уже есть отдельным файлом.
     */
    public static class ForceUtf8JsonInterceptor implements Interceptor {
        @Override
        public okhttp3.Response intercept(Chain chain) throws IOException {
            // твой реальный код в отдельном классе уже есть
            return chain.proceed(chain.request());
        }
    }

    /**
     * UTF-8 fixer для application/json без charset (если нужно).
     * Сейчас не используется напрямую, но можешь подключить вместо ForceUtf8JsonInterceptor.
     */

    // внутри ApiClient.java (как static class)
    static class BlockCmVideosDuringUploadInterceptor implements okhttp3.Interceptor {
        @Override
        public okhttp3.Response intercept(Chain chain) throws java.io.IOException {
            okhttp3.Request r = chain.request();
            String url = r.url().toString();

            if (UploadGate.isUploading()
                    && "GET".equalsIgnoreCase(r.method())
                    && url.contains("/api/content-manager/videos/")) {
                // Важно: лучше не бросать исключение (оно будет "красным" в логах),
                // а вернуть "фейковый" 204, чтобы приложение спокойно пережило.
                return new okhttp3.Response.Builder()
                        .request(r)
                        .protocol(okhttp3.Protocol.HTTP_1_1)
                        .code(204)
                        .message("Skipped during upload")
                        .body(okhttp3.ResponseBody.create(new byte[0], okhttp3.MediaType.get("text/plain")))
                        .build();
            }

            return chain.proceed(r);
        }
    }

}
