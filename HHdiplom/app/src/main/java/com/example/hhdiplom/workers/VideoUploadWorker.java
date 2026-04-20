package com.example.hhdiplom.workers;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.net.Uri;
import android.os.Build;
import android.util.Log;

import androidx.annotation.NonNull;
import androidx.core.app.NotificationCompat;
import androidx.work.Data;
import androidx.work.ForegroundInfo;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import com.example.hhdiplom.R;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ProgressRequestBody;
import com.example.hhdiplom.api.UploadGate;
import com.example.hhdiplom.models.VacancyVideo;
import com.example.hhdiplom.utils.UriFileUtils;

import java.io.File;

import okhttp3.MediaType;
import okhttp3.MultipartBody;
import okhttp3.RequestBody;
import retrofit2.Response;

public class VideoUploadWorker extends Worker {

    public static final String KEY_URI = "uri";
    public static final String KEY_VACANCY_ID = "vacancy_id";
    public static final String KEY_DESC = "desc";

    public static final String KEY_PROGRESS = "progress"; // 0..100
    public static final String KEY_ERROR = "error";

    private static final String TAG = "UPLOAD_WORKER";
    private static final String CHANNEL_ID = "upload_channel";
    private static final int NOTIF_ID = 42;

    public VideoUploadWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    @NonNull
    @Override
    public Result doWork() {
        try {
            Context ctx = getApplicationContext();

            // важно: prefs для токенов
            ApiClient.init(ctx);
            UploadGate.begin();

            String uriStr = getInputData().getString(KEY_URI);
            int vacancyId = getInputData().getInt(KEY_VACANCY_ID, 0);
            String desc = getInputData().getString(KEY_DESC);

            if (uriStr == null || uriStr.trim().isEmpty()) {
                return failure("uri is empty");
            }
            if (vacancyId <= 0) {
                return failure("vacancy_id invalid");
            }
            if (desc == null) desc = "";

            Uri uri = Uri.parse(uriStr);

            // foreground обязательно
            setForegroundAsync(createForegroundInfo(0));

            // 1) копируем Uri -> cache file (внутри worker, не activity)
            File file = UriFileUtils.copyUriToCache(ctx, uri);
            if (file == null || !file.exists() || file.length() <= 0) {
                return failure("cacheFile invalid");
            }

            Log.d(TAG, "cacheFile=" + file.getAbsolutePath() + " size=" + file.length());

            // 2) multipart + progress
            RequestBody raw = RequestBody.create(file, MediaType.parse("video/*"));

            ProgressRequestBody progressBody = new ProgressRequestBody(raw, (bytes, total) -> {
                int p = (total > 0) ? (int) ((bytes * 100L) / total) : 0;

                // отправляем прогресс в WorkManager observer
                setProgressAsync(new Data.Builder().putInt(KEY_PROGRESS, p).build());

                // обновляем нотификацию (не слишком часто — но тут уже ok)
                setForegroundAsync(createForegroundInfo(p));
            });

            MultipartBody.Part videoPart =
                    MultipartBody.Part.createFormData("video", file.getName(), progressBody);

            RequestBody vacancyBody =
                    RequestBody.create(String.valueOf(vacancyId), MediaType.parse("text/plain"));

            RequestBody descBody =
                    RequestBody.create(desc, MediaType.parse("text/plain"));
            Log.d("UPLOAD_WORKER", "about to execute upload call...");

            // 3) синхронный запрос
            Response<VacancyVideo> resp =
                    ApiClient.getApiService()
                            .uploadVideoAsCM(videoPart, vacancyBody, descBody)
                            .execute();
            Log.d("UPLOAD_WORKER", "upload finished. code=" + resp.code());

            if (resp.isSuccessful()) {
                setForegroundAsync(createForegroundInfo(100));
                return Result.success();
            } else {
                String err = "";
                try {
                    if (resp.errorBody() != null) err = resp.errorBody().string();
                } catch (Exception ignored) {}
                Log.e(TAG, "upload error code=" + resp.code() + " body=" + err);
                return failure("HTTP " + resp.code());
            }

        } catch (Exception e) {
            Log.e(TAG, "upload failed: " + e.getMessage(), e);
            return failure(e.getClass().getSimpleName() + ": " + e.getMessage());
        } finally {
            UploadGate.end();
        }
    }

    private Result failure(String msg) {
        Data out = new Data.Builder().putString(KEY_ERROR, msg).build();
        return Result.failure(out);
    }

    private int lastForegroundP = -1;
    private long lastForegroundTs = 0L;

    private void updateProgressThrottled(int p) {
        long now = System.currentTimeMillis();
        if (p == lastForegroundP) return;

        boolean step = (p == 0 || p == 100 || p % 5 == 0);
        boolean timeOk = (now - lastForegroundTs) > 500;

        if (step && timeOk) {
            lastForegroundP = p;
            lastForegroundTs = now;
            setForegroundAsync(createForegroundInfo(p));
            setProgressAsync(new Data.Builder().putInt("progress", p).build());
            Log.d("UPLOAD_WORKER", "progress=" + p + "%");
        }
    }


    private ForegroundInfo createForegroundInfo(int progress) {
        Context ctx = getApplicationContext();
        ensureChannel(ctx);

        String text = (progress >= 100)
                ? "Загрузка завершена"
                : ("Загрузка видео: " + progress + "%");

        Notification notif = new NotificationCompat.Builder(ctx, CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_launcher_foreground) // поменяй на свою иконку
                .setContentTitle("HR-Lab")
                .setContentText(text)
                .setOngoing(progress < 100)
                .setOnlyAlertOnce(true)
                .setProgress(100, Math.max(0, Math.min(100, progress)), false)
                .build();

        return new ForegroundInfo(NOTIF_ID, notif);
    }

    private void ensureChannel(Context ctx) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm.getNotificationChannel(CHANNEL_ID) != null) return;

        NotificationChannel ch = new NotificationChannel(
                CHANNEL_ID,
                "Загрузка видео",
                NotificationManager.IMPORTANCE_LOW
        );
        nm.createNotificationChannel(ch);
    }
}
