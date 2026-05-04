package com.example.hhdiplom.notifications;

import android.Manifest;
import android.app.Activity;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;

import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.ExistingWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;

import com.example.hhdiplom.R;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.workers.AppNotificationWorker;

import java.util.concurrent.TimeUnit;

public final class AppNotificationCoordinator {

    public static final String CHAT_CHANNEL_ID = "chat_updates";
    public static final String RESPONSE_CHANNEL_ID = "response_updates";
    public static final String PREF_NAME = "app_notification_state";
    public static final String KEY_TRACKED_USER_ID = "tracked_user_id";
    public static final String KEY_CHAT_STATE = "chat_state";
    public static final String KEY_RESPONSE_STATE = "response_state";
    public static final int REQUEST_NOTIFICATIONS_PERMISSION = 7001;

    private static final String UNIQUE_PERIODIC_WORK = "app_notification_periodic";
    private static final String UNIQUE_IMMEDIATE_WORK = "app_notification_immediate";

    private AppNotificationCoordinator() {
    }

    public static void schedule(Context context) {
        Context appContext = context.getApplicationContext();
        ApiClient.init(appContext);

        if (!ApiClient.isLoggedIn()) {
            onUserLoggedOut(appContext);
            return;
        }

        ensureChannels(appContext);

        Constraints constraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();

        OneTimeWorkRequest immediateRequest = new OneTimeWorkRequest.Builder(AppNotificationWorker.class)
                .setConstraints(constraints)
                .build();

        PeriodicWorkRequest periodicRequest = new PeriodicWorkRequest.Builder(
                AppNotificationWorker.class,
                15,
                TimeUnit.MINUTES
        ).setConstraints(constraints).build();

        WorkManager workManager = WorkManager.getInstance(appContext);
        workManager.enqueueUniqueWork(UNIQUE_IMMEDIATE_WORK, ExistingWorkPolicy.REPLACE, immediateRequest);
        workManager.enqueueUniquePeriodicWork(UNIQUE_PERIODIC_WORK, ExistingPeriodicWorkPolicy.UPDATE, periodicRequest);
    }

    public static void onUserLoggedOut(Context context) {
        Context appContext = context.getApplicationContext();
        WorkManager workManager = WorkManager.getInstance(appContext);
        workManager.cancelUniqueWork(UNIQUE_IMMEDIATE_WORK);
        workManager.cancelUniqueWork(UNIQUE_PERIODIC_WORK);
        getStatePreferences(appContext).edit().clear().apply();
    }

    public static void requestPermissionIfNeeded(Activity activity) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            return;
        }
        if (ContextCompat.checkSelfPermission(activity, Manifest.permission.POST_NOTIFICATIONS)
                == PackageManager.PERMISSION_GRANTED) {
            return;
        }

        ActivityCompat.requestPermissions(
                activity,
                new String[]{Manifest.permission.POST_NOTIFICATIONS},
                REQUEST_NOTIFICATIONS_PERMISSION
        );
    }

    public static boolean hasNotificationPermission(Context context) {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU
                || ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS)
                == PackageManager.PERMISSION_GRANTED;
    }

    public static SharedPreferences getStatePreferences(Context context) {
        return context.getApplicationContext().getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE);
    }

    public static void ensureChannels(Context context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return;
        }

        NotificationManager notificationManager =
                (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);

        if (notificationManager.getNotificationChannel(CHAT_CHANNEL_ID) == null) {
            NotificationChannel chatChannel = new NotificationChannel(
                    CHAT_CHANNEL_ID,
                    context.getString(R.string.notification_chat_channel_name),
                    NotificationManager.IMPORTANCE_HIGH
            );
            notificationManager.createNotificationChannel(chatChannel);
        }

        if (notificationManager.getNotificationChannel(RESPONSE_CHANNEL_ID) == null) {
            NotificationChannel responseChannel = new NotificationChannel(
                    RESPONSE_CHANNEL_ID,
                    context.getString(R.string.notification_response_channel_name),
                    NotificationManager.IMPORTANCE_DEFAULT
            );
            notificationManager.createNotificationChannel(responseChannel);
        }
    }
}
