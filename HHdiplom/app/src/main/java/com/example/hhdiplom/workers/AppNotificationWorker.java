package com.example.hhdiplom.workers;

import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.text.TextUtils;
import android.util.Log;

import androidx.annotation.NonNull;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import com.example.hhdiplom.R;
import com.example.hhdiplom.activities.ChatMessagesActivity;
import com.example.hhdiplom.activities.ResponseDetailsActivity;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.models.Chat;
import com.example.hhdiplom.models.ChatResponse;
import com.example.hhdiplom.models.ResponseItem;
import com.example.hhdiplom.models.ResponsesResponse;
import com.example.hhdiplom.notifications.AppNotificationCoordinator;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.util.Collections;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import retrofit2.Response;

public class AppNotificationWorker extends Worker {

    private static final String TAG = "APP_NOTIFICATIONS";

    public AppNotificationWorker(@NonNull Context context, @NonNull WorkerParameters workerParams) {
        super(context, workerParams);
    }

    @NonNull
    @Override
    public Result doWork() {
        Context context = getApplicationContext();
        ApiClient.init(context);

        if (!ApiClient.isLoggedIn()) {
            AppNotificationCoordinator.onUserLoggedOut(context);
            return Result.success();
        }

        SharedPreferences preferences = AppNotificationCoordinator.getStatePreferences(context);
        boolean resetState = ensureTrackedUser(preferences, ApiClient.getUserId());

        try {
            syncChatNotifications(context, preferences, resetState);
        } catch (IOException exception) {
            Log.w(TAG, "Chat notification sync failed", exception);
        }

        if (isApplicantUser()) {
            try {
                syncResponseNotifications(context, preferences, resetState);
            } catch (IOException exception) {
                Log.w(TAG, "Response notification sync failed", exception);
            }
        } else {
            saveMap(preferences, AppNotificationCoordinator.KEY_RESPONSE_STATE, new HashMap<String, String>());
        }

        return Result.success();
    }

    private boolean ensureTrackedUser(SharedPreferences preferences, int userId) {
        int storedUserId = preferences.getInt(AppNotificationCoordinator.KEY_TRACKED_USER_ID, -1);
        if (storedUserId == userId) {
            return false;
        }

        preferences.edit()
                .putInt(AppNotificationCoordinator.KEY_TRACKED_USER_ID, userId)
                .remove(AppNotificationCoordinator.KEY_CHAT_STATE)
                .remove(AppNotificationCoordinator.KEY_RESPONSE_STATE)
                .apply();
        return true;
    }

    private boolean isApplicantUser() {
        String userType = ApiClient.getUserType();
        return userType != null && userType.toLowerCase(Locale.getDefault()).contains("applicant");
    }

    private void syncChatNotifications(Context context,
                                       SharedPreferences preferences,
                                       boolean resetState) throws IOException {
        Response<ChatResponse> response = ApiClient.getApiService().getChats().execute();
        if (!response.isSuccessful() || response.body() == null) {
            return;
        }

        Map<String, String> previousState = loadMap(preferences, AppNotificationCoordinator.KEY_CHAT_STATE);
        boolean firstSync = resetState || previousState.isEmpty();
        Map<String, String> currentState = new HashMap<>();
        List<Chat> chats = response.body().getResults();
        if (chats == null) {
            chats = Collections.emptyList();
        }

        String incomingSenderType = isApplicantUser() ? "company" : "applicant";

        for (Chat chat : chats) {
            String key = String.valueOf(chat.getId());
            Chat.LastMessage lastMessage = chat.getLastMessage();
            String senderType = lastMessage != null ? safe(lastMessage.getSenderType()) : "";
            String createdAt = lastMessage != null ? safe(lastMessage.getCreatedAt()) : "";
            String text = lastMessage != null ? safe(lastMessage.getText()) : "";
            int unreadCount = Math.max(chat.getUnreadCount(), 0);

            String snapshot = senderType + "|" + createdAt + "|" + unreadCount + "|" + text;
            currentState.put(key, snapshot);

            if (firstSync) {
                continue;
            }

            String previousSnapshot = previousState.get(key);
            boolean hasChange = !TextUtils.equals(snapshot, previousSnapshot);
            if (hasChange
                    && unreadCount > 0
                    && incomingSenderType.equalsIgnoreCase(senderType)) {
                showChatNotification(context, chat, text);
            }
        }

        saveMap(preferences, AppNotificationCoordinator.KEY_CHAT_STATE, currentState);
    }

    private void syncResponseNotifications(Context context,
                                           SharedPreferences preferences,
                                           boolean resetState) throws IOException {
        Response<ResponsesResponse> response = ApiClient.getApiService().getResponses().execute();
        if (!response.isSuccessful() || response.body() == null) {
            return;
        }

        Map<String, String> previousState = loadMap(preferences, AppNotificationCoordinator.KEY_RESPONSE_STATE);
        boolean firstSync = resetState || previousState.isEmpty();
        Map<String, String> currentState = new HashMap<>();
        List<ResponseItem> responses = response.body().getResults();
        if (responses == null) {
            responses = Collections.emptyList();
        }

        for (ResponseItem responseItem : responses) {
            String key = String.valueOf(responseItem.getId());
            String snapshot = responseItem.getStatusId() + "|" + safe(responseItem.getStatusName());
            currentState.put(key, snapshot);

            if (firstSync) {
                continue;
            }

            String previousSnapshot = previousState.get(key);
            if (previousSnapshot != null && !TextUtils.equals(snapshot, previousSnapshot)) {
                showResponseNotification(context, responseItem);
            }
        }

        saveMap(preferences, AppNotificationCoordinator.KEY_RESPONSE_STATE, currentState);
    }

    private void showChatNotification(Context context, Chat chat, String messageText) {
        if (!AppNotificationCoordinator.hasNotificationPermission(context)) {
            return;
        }

        AppNotificationCoordinator.ensureChannels(context);

        Intent intent = ChatMessagesActivity.createIntent(
                context,
                chat.getId(),
                chat.getVacancyId(),
                chat.getCompanyName(),
                chat.getVacancyTitle()
        );
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);

        PendingIntent pendingIntent = PendingIntent.getActivity(
                context,
                10000 + chat.getId(),
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        String companyName = safe(chat.getCompanyName());
        if (companyName.isEmpty()) {
            companyName = context.getString(R.string.chat_title_fallback);
        }

        String contentText = messageText.trim().isEmpty()
                ? context.getString(R.string.notification_chat_text_fallback)
                : limitText(messageText, 120);

        NotificationCompat.Builder builder = new NotificationCompat.Builder(
                context,
                AppNotificationCoordinator.CHAT_CHANNEL_ID
        )
                .setSmallIcon(R.drawable.ic_messages)
                .setContentTitle(context.getString(R.string.notification_chat_title, companyName))
                .setContentText(contentText)
                .setSubText(safe(chat.getVacancyTitle()))
                .setStyle(new NotificationCompat.BigTextStyle().bigText(contentText))
                .setAutoCancel(true)
                .setContentIntent(pendingIntent)
                .setPriority(NotificationCompat.PRIORITY_HIGH);

        NotificationManagerCompat.from(context).notify(10000 + chat.getId(), builder.build());
    }

    private void showResponseNotification(Context context, ResponseItem responseItem) {
        if (!AppNotificationCoordinator.hasNotificationPermission(context)) {
            return;
        }

        AppNotificationCoordinator.ensureChannels(context);

        Intent intent = ResponseDetailsActivity.createIntent(
                context,
                responseItem.getId(),
                responseItem.getVacancyId(),
                responseItem.getVacancyPosition(),
                responseItem.getCompanyName(),
                responseItem.getStatusName(),
                responseItem.getResponseDate(),
                responseItem.getApplicantName()
        );
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);

        PendingIntent pendingIntent = PendingIntent.getActivity(
                context,
                20000 + responseItem.getId(),
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        String vacancyTitle = safe(responseItem.getVacancyPosition());
        if (vacancyTitle.isEmpty()) {
            vacancyTitle = context.getString(R.string.response_no_vacancy);
        }

        String contentText = context.getString(
                R.string.notification_response_text,
                vacancyTitle,
                safe(responseItem.getStatusName())
        );

        NotificationCompat.Builder builder = new NotificationCompat.Builder(
                context,
                AppNotificationCoordinator.RESPONSE_CHANNEL_ID
        )
                .setSmallIcon(R.drawable.ic_responses)
                .setContentTitle(context.getString(R.string.notification_response_title))
                .setContentText(contentText)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(contentText))
                .setAutoCancel(true)
                .setContentIntent(pendingIntent)
                .setPriority(NotificationCompat.PRIORITY_DEFAULT);

        NotificationManagerCompat.from(context).notify(20000 + responseItem.getId(), builder.build());
    }

    private Map<String, String> loadMap(SharedPreferences preferences, String key) {
        String rawValue = preferences.getString(key, null);
        Map<String, String> values = new HashMap<>();
        if (rawValue == null || rawValue.trim().isEmpty()) {
            return values;
        }

        try {
            JSONObject jsonObject = new JSONObject(rawValue);
            Iterator<String> keys = jsonObject.keys();
            while (keys.hasNext()) {
                String mapKey = keys.next();
                values.put(mapKey, jsonObject.optString(mapKey, ""));
            }
        } catch (JSONException exception) {
            Log.w(TAG, "Failed to parse notification state for key=" + key, exception);
        }
        return values;
    }

    private void saveMap(SharedPreferences preferences, String key, Map<String, String> values) {
        JSONObject jsonObject = new JSONObject();
        for (Map.Entry<String, String> entry : values.entrySet()) {
            try {
                jsonObject.put(entry.getKey(), entry.getValue());
            } catch (JSONException exception) {
                Log.w(TAG, "Failed to persist notification state for key=" + key, exception);
            }
        }
        preferences.edit().putString(key, jsonObject.toString()).apply();
    }

    private String limitText(String value, int maxLength) {
        if (value == null) {
            return "";
        }

        String normalized = value.trim().replace('\n', ' ');
        if (normalized.length() <= maxLength) {
            return normalized;
        }
        return normalized.substring(0, Math.max(0, maxLength - 1)).trim() + "...";
    }

    private String safe(String value) {
        return value == null ? "" : value;
    }
}
