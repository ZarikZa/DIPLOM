package com.example.hhdiplom.activities;

import android.content.Intent;
import android.os.Bundle;
import android.text.TextUtils;
import android.view.View;
import android.widget.*;
import androidx.appcompat.app.AppCompatActivity;
import com.example.hhdiplom.R;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.managers.ResponseManager;
import com.example.hhdiplom.models.Complaint;
import com.example.hhdiplom.models.ComplaintCreateRequest;
import com.example.hhdiplom.models.ComplaintListResponse;
import com.example.hhdiplom.models.VacancyDetails;
import com.example.hhdiplom.models.ToggleFavoriteRequest;
import com.example.hhdiplom.models.ToggleFavoriteResponse;
import com.example.hhdiplom.utils.ProfanityValidator;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;
public class VacancyDetailsActivity extends AppCompatActivity {

    private TextView tvPosition, tvCompany, tvCity, tvDescription;
    private TextView tvViews, tvCreatedAt, tvRequirements, tvResponsibilities;
    private TextView tvConditions, tvSkills, tvEducation;
    private TextView tagSalary, tagExperience, tagCategory, tagEmployment, tagSchedule;
    private LinearLayout extraTagsContainer;
    private View cardRequirements, cardResponsibilities, cardConditions, cardSkills, cardEducation;
    private ProgressBar progressBar;
    private ImageButton btnBack, btnFavorite, btnAddToFavorites;
    private Button btnApply;
    private ImageButton btnReport;
    private boolean hasComplained = false;
    private ApiService apiService;
    private int vacancyId;
    private boolean isFavorite = false;
    private boolean hasApplied = false; // Добавляем переменную для статуса отклика

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_vacancy_details);

        // Получаем ID вакансии из Intent
        vacancyId = getIntent().getIntExtra("vacancy_id", -1);
        if (vacancyId == -1) {
            Toast.makeText(this, getString(R.string.error_with_code, -1), Toast.LENGTH_SHORT).show();
            finish();
            return;
        }

        // Инициализируем API
        ApiClient.init(this);
        apiService = ApiClient.getApiService();

        initViews();
        setupListeners();
        loadVacancyDetails();
        checkComplaintStatus();

    }



    private void initViews() {
        // Текстовые поля
        tvPosition = findViewById(R.id.tvPosition);
        tvCompany = findViewById(R.id.tvCompany);
        tvCity = findViewById(R.id.tvCity);
        tvDescription = findViewById(R.id.tvDescription);
        tvViews = findViewById(R.id.tvViews);
        tvCreatedAt = findViewById(R.id.tvCreatedAt);

        // Теги
        tagSalary = findViewById(R.id.tagSalary);
        tagExperience = findViewById(R.id.tagExperience);
        tagCategory = findViewById(R.id.tagCategory);
        tagEmployment = findViewById(R.id.tagEmployment);
        tagSchedule = findViewById(R.id.tagSchedule);
        extraTagsContainer = findViewById(R.id.extraTagsContainer);

        // Карточки (скрытые по умолчанию)
        cardRequirements = findViewById(R.id.cardRequirements);
        cardResponsibilities = findViewById(R.id.cardResponsibilities);
        cardConditions = findViewById(R.id.cardConditions);
        cardSkills = findViewById(R.id.cardSkills);
        cardEducation = findViewById(R.id.cardEducation);

        // Текст внутри карточек
        tvRequirements = findViewById(R.id.tvRequirements);
        tvResponsibilities = findViewById(R.id.tvResponsibilities);
        tvConditions = findViewById(R.id.tvConditions);
        tvSkills = findViewById(R.id.tvSkills);
        tvEducation = findViewById(R.id.tvEducation);

        // Кнопки
        btnBack = findViewById(R.id.btnBack);
        btnFavorite = findViewById(R.id.btnFavorite);
        btnApply = findViewById(R.id.btnApply);
        btnAddToFavorites = findViewById(R.id.btnAddToFavorites);
        btnReport = findViewById(R.id.btnReport);

        // Прогресс бар
        progressBar = findViewById(R.id.progressBar);
    }

    private void setupListeners() {
        btnBack.setOnClickListener(v -> onBackPressed());

        btnFavorite.setOnClickListener(v -> toggleFavorite());
        btnAddToFavorites.setOnClickListener(v -> toggleFavorite());

        btnApply.setOnClickListener(v -> {
            if (!hasApplied) {
                applyForVacancy();
            }
        });

        btnReport.setOnClickListener(v -> {
            if (!hasComplained) showComplaintDialog();
        });

    }

    private void showComplaintDialog() {
        // Варианты должны совпадать с тем, что на бэке: spam/fraud/inappropriate/discrimination/false_info/other
        final String[] labels = getResources().getStringArray(R.array.vacancy_complaint_labels);
        final String[] values = {"spam", "fraud", "inappropriate", "discrimination", "false_info", "other"};

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = (int) (16 * getResources().getDisplayMetrics().density);
        root.setPadding(pad, pad, pad, pad);

        TextView tv = new TextView(this);
        tv.setText(R.string.vacancy_complaint_reason);
        root.addView(tv);

        Spinner spinner = new Spinner(this);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, labels);
        spinner.setAdapter(adapter);
        root.addView(spinner);

        EditText etDesc = new EditText(this);
        etDesc.setHint(R.string.vacancy_complaint_hint);
        etDesc.setMinLines(3);
        etDesc.setMaxLines(6);
        root.addView(etDesc);

        new androidx.appcompat.app.AlertDialog.Builder(this)
                .setTitle(R.string.vacancy_complaint_title)
                .setView(root)
                .setNegativeButton(R.string.cancel, null)
                .setPositiveButton(R.string.send, (d, which) -> {
                    int idx = spinner.getSelectedItemPosition();
                    String type = values[Math.max(0, idx)];
                    String desc = etDesc.getText() != null ? etDesc.getText().toString().trim() : "";
                    if (!desc.isEmpty() && ProfanityValidator.containsProfanity(desc)) {
                        Toast.makeText(this, ProfanityValidator.DEFAULT_ERROR_MESSAGE, Toast.LENGTH_SHORT).show();
                        return;
                    }
                    sendComplaint(type, desc);
                })
                .show();
    }

    private void checkComplaintStatus() {
        apiService.getMyComplaints(vacancyId).enqueue(new Callback<ComplaintListResponse>() {
            @Override
            public void onResponse(Call<ComplaintListResponse> call, Response<ComplaintListResponse> response) {
                if (response.isSuccessful() && response.body() != null) {
                    List<Complaint> results = response.body().getResults();
                    hasComplained = results != null && !results.isEmpty();
                    updateReportButton();
                } else {
                    android.util.Log.d("ComplaintCheck", "code=" + response.code());
                }
            }

            @Override
            public void onFailure(Call<ComplaintListResponse> call, Throwable t) {
                android.util.Log.e("ComplaintCheck", "FAIL: " + t.getMessage(), t);
            }
        });
    }



    private void sendComplaint(String complaintType, String description) {
        btnReport.setEnabled(false);

        ComplaintCreateRequest body = new ComplaintCreateRequest(vacancyId, complaintType, description);

        apiService.createComplaint(body).enqueue(new Callback<Complaint>() {
            @Override
            public void onResponse(Call<Complaint> call, Response<Complaint> response) {
                if (response.isSuccessful()) {
                    hasComplained = true;
                    Toast.makeText(VacancyDetailsActivity.this, getString(R.string.vacancy_complaint_sent), Toast.LENGTH_SHORT).show();
                    updateReportButton();
                    return;
                }

                String err = "";
                try {
                    if (response.errorBody() != null) err = response.errorBody().string();
                } catch (Exception ignored) {}

                if (response.code() == 400 && (err.contains("unique") || err.contains("already") || err.contains("существ"))) {
                    hasComplained = true;
                    Toast.makeText(VacancyDetailsActivity.this, getString(R.string.vacancy_complaint_already_sent), Toast.LENGTH_SHORT).show();
                    updateReportButton();
                } else if (response.code() == 401) {
                    Toast.makeText(VacancyDetailsActivity.this, getString(R.string.vacancy_complaint_auth_required), Toast.LENGTH_SHORT).show();
                    btnReport.setEnabled(true);
                } else {
                    Toast.makeText(VacancyDetailsActivity.this, getString(R.string.vacancy_complaint_send_error, response.code()), Toast.LENGTH_SHORT).show();
                    btnReport.setEnabled(true);
                }
            }

            @Override
            public void onFailure(Call<Complaint> call, Throwable t) {
                Toast.makeText(VacancyDetailsActivity.this, getString(R.string.error_network_with_message, t.getMessage()), Toast.LENGTH_SHORT).show();
                btnReport.setEnabled(true);
            }
        });
    }

    private void updateReportButton() {
        if (hasComplained) {
            btnReport.setEnabled(false);
            btnReport.setAlpha(0.5f);
            // если хочешь — поменять иконку на "отправлено"
            // btnReport.setImageResource(R.drawable.ic_report_done);
        } else {
            btnReport.setEnabled(true);
            btnReport.setAlpha(1f);
        }
    }


    private void loadVacancyDetails() {
        progressBar.setVisibility(View.VISIBLE);

        Call<VacancyDetails> call = apiService.getVacancyDetails(vacancyId);
        call.enqueue(new Callback<VacancyDetails>() {
            @Override
            public void onResponse(Call<VacancyDetails> call, Response<VacancyDetails> response) {
                progressBar.setVisibility(View.GONE);

                if (response.isSuccessful() && response.body() != null) {
                    VacancyDetails vacancy = response.body();
                    displayVacancyDetails(vacancy);
                } else {
                    handleError(response.code());
                }
            }

            @Override
            public void onFailure(Call<VacancyDetails> call, Throwable t) {
                progressBar.setVisibility(View.GONE);
                Toast.makeText(VacancyDetailsActivity.this,
                        getString(R.string.error_network_with_message, t.getMessage()),
                        Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void displayVacancyDetails(VacancyDetails vacancy) {
        // Основная информация
        tvPosition.setText(vacancy.getPosition());
        tvCompany.setText(vacancy.getCompanyName());
        tvCity.setText(vacancy.getCity());

        // Описание
        if (!TextUtils.isEmpty(vacancy.getDescription())) {
            tvDescription.setText(vacancy.getDescription());
        } else {
            tvDescription.setText(getString(R.string.profile_not_specified));
        }

        // Теги
        if (!TextUtils.isEmpty(vacancy.getSalary())) {
            tagSalary.setText(vacancy.getSalary());
            tagSalary.setVisibility(View.VISIBLE);
        } else {
            tagSalary.setVisibility(View.GONE);
        }

        if (!TextUtils.isEmpty(vacancy.getExperience())) {
            tagExperience.setText(vacancy.getExperience());
            tagExperience.setVisibility(View.VISIBLE);
        } else {
            tagExperience.setVisibility(View.GONE);
        }

        if (!TextUtils.isEmpty(vacancy.getCategory())) {
            tagCategory.setText(vacancy.getCategory());
            tagCategory.setVisibility(View.VISIBLE);
        } else {
            tagCategory.setVisibility(View.GONE);
        }

        // Дополнительные теги
        boolean hasExtraTags = false;
        if (!TextUtils.isEmpty(vacancy.getEmploymentType())) {
            tagEmployment.setText(vacancy.getEmploymentType());
            tagEmployment.setVisibility(View.VISIBLE);
            hasExtraTags = true;
        } else {
            tagEmployment.setVisibility(View.GONE);
        }

        if (!TextUtils.isEmpty(vacancy.getWorkSchedule())) {
            tagSchedule.setText(vacancy.getWorkSchedule());
            tagSchedule.setVisibility(View.VISIBLE);
            hasExtraTags = true;
        } else {
            tagSchedule.setVisibility(View.GONE);
        }

        extraTagsContainer.setVisibility(hasExtraTags ? View.VISIBLE : View.GONE);

        // Статистика
        tvViews.setText(getString(R.string.video_views_count, vacancy.getViewsCount()));

        if (!TextUtils.isEmpty(vacancy.getCreatedAt())) {
            try {
                SimpleDateFormat apiFormat = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.getDefault());
                SimpleDateFormat displayFormat = new SimpleDateFormat("dd MMM yyyy", Locale.getDefault());
                Date date = apiFormat.parse(vacancy.getCreatedAt());
                tvCreatedAt.setText(displayFormat.format(date));
            } catch (Exception e) {
                tvCreatedAt.setText(vacancy.getCreatedAt());
            }
        }

        // Дополнительные секции
        setupOptionalSection(cardRequirements, tvRequirements, vacancy.getRequirements());
        setupOptionalSection(cardResponsibilities, tvResponsibilities, vacancy.getResponsibilities());
        setupOptionalSection(cardConditions, tvConditions, vacancy.getConditions());
        setupOptionalSection(cardSkills, tvSkills, vacancy.getSkills());
        setupOptionalSection(cardEducation, tvEducation, vacancy.getEducation());

        // Получаем статус отклика
        hasApplied = vacancy.isHasApplied();
        updateApplyButton();

        // Проверяем, в избранном ли вакансия
        isFavorite = vacancy.isFavorite();
        updateFavoriteIcon();
        updateReportButton();
    }

    private void setupOptionalSection(View cardView, TextView textView, String content) {
        if (!TextUtils.isEmpty(content) && !content.equals("null")) {
            textView.setText(content);
            cardView.setVisibility(View.VISIBLE);
        } else {
            cardView.setVisibility(View.GONE);
        }
    }

    private void updateApplyButton() {
        if (hasApplied) {
            // Пользователь уже откликнулся
            btnApply.setText(R.string.video_apply_sent);
            btnApply.setBackgroundColor(getResources().getColor(R.color.gray));
            btnApply.setTextColor(getResources().getColor(R.color.white));
            btnApply.setEnabled(false);
        } else {
            // Пользователь еще не откликался
            btnApply.setText(R.string.video_apply_button);
            btnApply.setBackgroundColor(getResources().getColor(R.color.primary));
            btnApply.setTextColor(getResources().getColor(R.color.white));
            btnApply.setEnabled(true);
        }
    }

    private void toggleFavorite() {
        // Оптимистичное обновление UI
        final boolean prev = isFavorite;
        isFavorite = !isFavorite;
        updateFavoriteIcon();

        apiService.toggleFavorite(new ToggleFavoriteRequest(vacancyId))
                .enqueue(new Callback<ToggleFavoriteResponse>() {
                    @Override
                    public void onResponse(Call<ToggleFavoriteResponse> call, Response<ToggleFavoriteResponse> response) {
                        if (response.isSuccessful() && response.body() != null) {
                            isFavorite = response.body().isFavorite();
                            updateFavoriteIcon();
                            String message = isFavorite
                                    ? getString(R.string.favorite_added)
                                    : getString(R.string.favorite_removed);
                            Toast.makeText(VacancyDetailsActivity.this, message, Toast.LENGTH_SHORT).show();
                        } else {
                            // откат
                            isFavorite = prev;
                            updateFavoriteIcon();
                            Toast.makeText(VacancyDetailsActivity.this, getString(R.string.favorite_error_code, response.code()), Toast.LENGTH_SHORT).show();
                        }
                    }

                    @Override
                    public void onFailure(Call<ToggleFavoriteResponse> call, Throwable t) {
                        // откат
                        isFavorite = prev;
                        updateFavoriteIcon();
                        Toast.makeText(VacancyDetailsActivity.this, getString(R.string.error_network_with_message, t.getMessage()), Toast.LENGTH_SHORT).show();
                    }
                });
    }
private void updateFavoriteIcon() {
        if (isFavorite) {
            btnFavorite.setImageResource(R.drawable.ic_favorite_filled);
            btnAddToFavorites.setImageResource(R.drawable.ic_favorite_filled);
            btnFavorite.setColorFilter(getColor(R.color.accent));
            btnAddToFavorites.setColorFilter(getColor(R.color.accent));
        } else {
            btnFavorite.setImageResource(R.drawable.ic_favorite_border);
            btnAddToFavorites.setImageResource(R.drawable.ic_favorite_border);
            btnFavorite.setColorFilter(getColor(R.color.accent_light));
            btnAddToFavorites.setColorFilter(getColor(R.color.accent_light));
        }
    }

    private void applyForVacancy() {
        String position = tvPosition.getText().toString();
        String company = tvCompany.getText().toString();

        ResponseManager.showResponseDialog(
                this,
                position,
                company,
                vacancyId,
                new ResponseManager.ResponseCallback() {
                    @Override
                    public void onSuccess(int responseId) {
                        runOnUiThread(() -> {
                            // Обновляем статус
                            hasApplied = true;
                            updateApplyButton();

                            // Показываем уведомление
                            Toast.makeText(VacancyDetailsActivity.this,
                                    getString(R.string.vacancy_response_sent_wait),
                                    Toast.LENGTH_LONG).show();
                        });
                    }

                    @Override
                    public void onFailure(String error) {
                        runOnUiThread(() -> {
                            if (error.equals("already_responded")) {
                                // На всякий случай, если уже откликались
                                hasApplied = true;
                                updateApplyButton();
                                Toast.makeText(VacancyDetailsActivity.this,
                                        getString(R.string.response_already_exists),
                                        Toast.LENGTH_SHORT).show();
                            }
                        });
                    }
                }
        );
    }

    private void handleError(int errorCode) {
        switch (errorCode) {
            case 404:
                Toast.makeText(this, getString(R.string.responses_error_not_found), Toast.LENGTH_SHORT).show();
                finish();
                break;
            case 401:
                Toast.makeText(this, getString(R.string.responses_error_auth), Toast.LENGTH_SHORT).show();
                finish();
                break;
            default:
                Toast.makeText(this, getString(R.string.error_with_code, errorCode), Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    public void onBackPressed() {
        super.onBackPressed();
        overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
    }
}
