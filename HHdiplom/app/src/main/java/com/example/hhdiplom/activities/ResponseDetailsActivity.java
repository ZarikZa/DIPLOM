package com.example.hhdiplom.activities;

import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.text.TextUtils;
import android.widget.Button;
import android.widget.ImageButton;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;

import com.example.hhdiplom.R;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.models.ResponseItem;

import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Arrays;
import java.util.Date;
import java.util.List;
import java.util.Locale;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class ResponseDetailsActivity extends AppCompatActivity {

    public static final String EXTRA_RESPONSE_ID = "response_id";
    public static final String EXTRA_VACANCY_ID = "vacancy_id";
    public static final String EXTRA_VACANCY_POSITION = "vacancy_position";
    public static final String EXTRA_COMPANY_NAME = "company_name";
    public static final String EXTRA_STATUS_NAME = "status_name";
    public static final String EXTRA_RESPONSE_DATE = "response_date";
    public static final String EXTRA_APPLICANT_NAME = "applicant_name";

    private static final String FILTER_INVITATION = "invitation";

    private TextView tvResponseId;
    private TextView tvPosition;
    private TextView tvCompany;
    private TextView tvStatus;
    private TextView tvDate;
    private TextView tvApplicant;
    private ProgressBar progressBar;
    private Button btnOpenVacancy;
    private Button btnAcceptInvite;

    private ApiService apiService;
    private int responseId;
    private int vacancyId;

    public static Intent createIntent(@NonNull Context context, @NonNull ResponseItem response) {
        return createIntent(
                context,
                response.getId(),
                response.getVacancyId(),
                response.getVacancyPosition(),
                response.getCompanyName(),
                response.getStatusName(),
                response.getResponseDate(),
                response.getApplicantName()
        );
    }

    public static Intent createIntent(@NonNull Context context,
                                      int responseId,
                                      int vacancyId,
                                      String vacancyPosition,
                                      String companyName,
                                      String statusName,
                                      String responseDate,
                                      String applicantName) {
        Intent intent = new Intent(context, ResponseDetailsActivity.class);
        intent.putExtra(EXTRA_RESPONSE_ID, responseId);
        intent.putExtra(EXTRA_VACANCY_ID, vacancyId);
        intent.putExtra(EXTRA_VACANCY_POSITION, vacancyPosition);
        intent.putExtra(EXTRA_COMPANY_NAME, companyName);
        intent.putExtra(EXTRA_STATUS_NAME, statusName);
        intent.putExtra(EXTRA_RESPONSE_DATE, responseDate);
        intent.putExtra(EXTRA_APPLICANT_NAME, applicantName);
        return intent;
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_response_details);

        ApiClient.init(this);
        apiService = ApiClient.getApiService();

        initViews();
        bindInitialExtras();
        setupActions();
        loadResponseDetails();
    }

    private void initViews() {
        ImageButton btnBack = findViewById(R.id.btnBackResponseDetails);
        tvResponseId = findViewById(R.id.tvResponseId);
        tvPosition = findViewById(R.id.tvResponsePosition);
        tvCompany = findViewById(R.id.tvResponseCompany);
        tvStatus = findViewById(R.id.tvResponseStatus);
        tvDate = findViewById(R.id.tvResponseDate);
        tvApplicant = findViewById(R.id.tvResponseApplicant);
        progressBar = findViewById(R.id.progressBarResponseDetails);
        btnOpenVacancy = findViewById(R.id.btnOpenVacancyFromResponse);
        btnAcceptInvite = findViewById(R.id.btnAcceptInvite);

        btnBack.setOnClickListener(v -> finish());
    }

    private void bindInitialExtras() {
        Intent intent = getIntent();
        responseId = intent.getIntExtra(EXTRA_RESPONSE_ID, -1);
        vacancyId = intent.getIntExtra(EXTRA_VACANCY_ID, -1);

        if (responseId <= 0) {
            Toast.makeText(this, getString(R.string.error_with_code, -1), Toast.LENGTH_SHORT).show();
            finish();
            return;
        }

        tvResponseId.setText(String.format(Locale.getDefault(), "#%d", responseId));

        applyResponse(
                intent.getStringExtra(EXTRA_VACANCY_POSITION),
                intent.getStringExtra(EXTRA_COMPANY_NAME),
                intent.getStringExtra(EXTRA_STATUS_NAME),
                intent.getStringExtra(EXTRA_RESPONSE_DATE),
                intent.getStringExtra(EXTRA_APPLICANT_NAME),
                vacancyId
        );
    }

    private void setupActions() {
        btnOpenVacancy.setOnClickListener(v -> {
            if (vacancyId <= 0) {
                return;
            }
            Intent intent = new Intent(this, VacancyDetailsActivity.class);
            intent.putExtra("vacancy_id", vacancyId);
            startActivity(intent);
        });

        btnAcceptInvite.setOnClickListener(v ->
                Toast.makeText(this, getString(R.string.responses_invite_pending), Toast.LENGTH_SHORT).show()
        );
    }

    private void loadResponseDetails() {
        if (responseId <= 0) {
            return;
        }

        progressBar.setVisibility(android.view.View.VISIBLE);
        apiService.getResponseDetails(responseId).enqueue(new Callback<ResponseItem>() {
            @Override
            public void onResponse(@NonNull Call<ResponseItem> call, @NonNull Response<ResponseItem> response) {
                progressBar.setVisibility(android.view.View.GONE);
                if (response.isSuccessful() && response.body() != null) {
                    ResponseItem details = response.body();
                    applyResponse(
                            details.getVacancyPosition(),
                            details.getCompanyName(),
                            details.getStatusName(),
                            details.getResponseDate(),
                            details.getApplicantName(),
                            details.getVacancyId()
                    );
                }
            }

            @Override
            public void onFailure(@NonNull Call<ResponseItem> call, @NonNull Throwable t) {
                progressBar.setVisibility(android.view.View.GONE);
            }
        });
    }

    private void applyResponse(String vacancyPosition,
                               String companyName,
                               String statusName,
                               String responseDate,
                               String applicantName,
                               int vacancyIdFromResponse) {
        if (vacancyIdFromResponse > 0) {
            vacancyId = vacancyIdFromResponse;
        }

        tvPosition.setText(orFallback(vacancyPosition, getString(R.string.response_no_vacancy)));
        tvCompany.setText(orFallback(companyName, getString(R.string.response_no_company)));
        tvStatus.setText(orFallback(statusName, getString(R.string.response_status_sent)));
        tvDate.setText(formatDate(responseDate));
        tvApplicant.setText(orFallback(applicantName, getString(R.string.profile_user_fallback)));

        StatusStyle statusStyle = getStatusStyle(statusName);
        tvStatus.setBackgroundResource(statusStyle.backgroundRes);
        tvStatus.setTextColor(ContextCompat.getColor(this, statusStyle.textColorRes));

        btnOpenVacancy.setEnabled(vacancyId > 0);
        btnOpenVacancy.setAlpha(vacancyId > 0 ? 1f : 0.5f);
        btnAcceptInvite.setVisibility(FILTER_INVITATION.equals(classifyStatus(statusName))
                ? android.view.View.VISIBLE
                : android.view.View.GONE);
    }

    private String formatDate(String rawDate) {
        if (TextUtils.isEmpty(rawDate)) {
            return getString(R.string.response_date_unknown);
        }

        List<String> patterns = Arrays.asList(
                "yyyy-MM-dd'T'HH:mm:ss.SSSXXX",
                "yyyy-MM-dd'T'HH:mm:ssXXX",
                "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",
                "yyyy-MM-dd'T'HH:mm:ss'Z'",
                "yyyy-MM-dd'T'HH:mm:ss"
        );

        for (String pattern : patterns) {
            try {
                SimpleDateFormat parser = new SimpleDateFormat(pattern, Locale.US);
                Date date = parser.parse(rawDate);
                if (date != null) {
                    SimpleDateFormat display = new SimpleDateFormat("dd.MM.yyyy HH:mm", Locale.getDefault());
                    return display.format(date);
                }
            } catch (ParseException ignored) {
            }
        }

        return rawDate;
    }

    private String classifyStatus(String rawStatus) {
        String status = rawStatus == null ? "" : rawStatus.toLowerCase(Locale.getDefault());

        if (status.contains("invite")
                || status.contains("priglash")
                || status.contains("\u043f\u0440\u0438\u0433\u043b\u0430\u0448")) {
            return FILTER_INVITATION;
        }

        if (status.contains("reject")
                || status.contains("otkaz")
                || status.contains("\u043e\u0442\u043a\u0430\u0437")) {
            return "rejected";
        }

        if (status.contains("progress")
                || status.contains("review")
                || status.contains("interview")
                || status.contains("process")
                || status.contains("\u043f\u0440\u043e\u0446\u0435\u0441\u0441")
                || status.contains("\u0440\u0430\u0441\u0441\u043c\u043e\u0442\u0440")
                || status.contains("\u0438\u043d\u0442\u0435\u0440\u0432\u044c\u044e")) {
            return "progress";
        }

        return "sent";
    }

    private StatusStyle getStatusStyle(String rawStatus) {
        String status = rawStatus == null ? "" : rawStatus.toLowerCase(Locale.getDefault());

        if (status.contains("invite")
                || status.contains("priglash")
                || status.contains("\u043f\u0440\u0438\u0433\u043b\u0430\u0448")) {
            return new StatusStyle(R.drawable.bg_status_success, R.color.status_success_text);
        }

        if (status.contains("reject")
                || status.contains("otkaz")
                || status.contains("\u043e\u0442\u043a\u0430\u0437")) {
            return new StatusStyle(R.drawable.bg_status_error, R.color.status_error_text);
        }

        if (status.contains("progress")
                || status.contains("review")
                || status.contains("interview")
                || status.contains("process")
                || status.contains("\u043f\u0440\u043e\u0446\u0435\u0441\u0441")
                || status.contains("\u0440\u0430\u0441\u0441\u043c\u043e\u0442\u0440")
                || status.contains("\u0438\u043d\u0442\u0435\u0440\u0432\u044c\u044e")) {
            return new StatusStyle(R.drawable.bg_status_warning, R.color.status_warning_text);
        }

        if (status.contains("sent")
                || status.contains("new")
                || status.contains("otprav")
                || status.contains("\u043e\u0442\u043f\u0440\u0430\u0432")) {
            return new StatusStyle(R.drawable.bg_status_info, R.color.status_info_text);
        }

        return new StatusStyle(R.drawable.bg_status_neutral, R.color.status_neutral_text);
    }

    private String orFallback(String value, String fallback) {
        if (value == null || value.trim().isEmpty()) {
            return fallback;
        }
        return value.trim();
    }

    private static class StatusStyle {
        final int backgroundRes;
        final int textColorRes;

        StatusStyle(int backgroundRes, int textColorRes) {
            this.backgroundRes = backgroundRes;
            this.textColorRes = textColorRes;
        }
    }
}
