package com.example.hhdiplom.managers;

import android.content.Context;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;

import com.example.hhdiplom.R;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.models.CheckResponse;
import com.example.hhdiplom.models.ResponseRequest;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class ResponseManager {

    public interface ResponseCallback {
        void onSuccess(int responseId);
        void onFailure(String error);
    }

    public static void checkIfResponded(Context context, int vacancyId, ResponseCallback callback) {
        ApiService apiService = ApiClient.getApiService();

        apiService.checkResponse(vacancyId).enqueue(new Callback<CheckResponse>() {
            @Override
            public void onResponse(Call<CheckResponse> call, Response<CheckResponse> response) {
                if (response.isSuccessful() && response.body() != null) {
                    CheckResponse checkResponse = response.body();
                    if (checkResponse.isHasResponded()) {
                        // Уже откликнулись
                        callback.onSuccess(checkResponse.getResponseId());
                    } else {
                        // Не откликались
                        callback.onFailure("not_responded");
                    }
                } else {
                    callback.onFailure("check_failed");
                }
            }

            @Override
            public void onFailure(Call<CheckResponse> call, Throwable t) {
                callback.onFailure(t.getMessage());
            }
        });
    }

    public static void showResponseDialog(Context context, String position, String company,
                                          int vacancyId, ResponseCallback callback) {
        AlertDialog.Builder builder = new AlertDialog.Builder(context);
        builder.setTitle(R.string.response_dialog_title);
        builder.setMessage(context.getString(R.string.response_dialog_message, position, company));

        builder.setPositiveButton(R.string.response_dialog_positive, (dialog, which) -> {
            sendResponse(context, vacancyId, callback);
        });

        builder.setNegativeButton(R.string.cancel, null);
        builder.show();
    }

    public static void sendResponse(Context context, int vacancyId, ResponseCallback callback) {
        ApiService apiService = ApiClient.getApiService();

        ResponseRequest request = new ResponseRequest(vacancyId);
        Call<Void> call = apiService.createResponse(request);
        call.enqueue(new Callback<Void>() {
            @Override
            public void onResponse(Call<Void> call, Response<Void> response) {
                if (response.isSuccessful()) {
                    Toast.makeText(context, context.getString(R.string.response_sent_success), Toast.LENGTH_SHORT).show();
                    if (callback != null) {
                        callback.onSuccess(0);
                    }
                } else if (response.code() == 400) {
                    // Уже откликались или другая ошибка
                    if (callback != null) {
                        callback.onFailure("already_responded");
                    }
                } else {
                    Toast.makeText(context,
                            context.getString(R.string.response_error_send_code, response.code()),
                            Toast.LENGTH_SHORT).show();
                    if (callback != null) {
                        callback.onFailure("error_" + response.code());
                    }
                }
            }

            @Override
            public void onFailure(Call<Void> call, Throwable t) {
                Toast.makeText(context,
                        context.getString(R.string.error_network_with_message, t.getMessage()),
                        Toast.LENGTH_SHORT).show();
                if (callback != null) {
                    callback.onFailure(t.getMessage());
                }
            }
        });
    }

    public static void updateResponseStatus(Context context, int vacancyId,
                                            ResponseCallback callback) {
        checkIfResponded(context, vacancyId, new ResponseCallback() {
            @Override
            public void onSuccess(int responseId) {
                // Можно обновить UI - показать, что уже откликнулись
                if (context != null) {
                    Toast.makeText(context,
                            context.getString(R.string.response_already_applied_toast),
                            Toast.LENGTH_SHORT).show();
                }
            }

            @Override
            public void onFailure(String error) {
                // Не откликались, можно предложить откликнуться
            }
        });
    }
}
