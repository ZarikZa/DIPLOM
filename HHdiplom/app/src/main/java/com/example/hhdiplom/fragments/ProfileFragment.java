package com.example.hhdiplom.fragments;

import android.app.Activity;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.text.TextUtils;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AlertDialog;
import androidx.core.content.ContextCompat;
import androidx.fragment.app.Fragment;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.bumptech.glide.Glide;
import com.example.hhdiplom.R;
import com.example.hhdiplom.activities.ChangePasswordActivity;
import com.example.hhdiplom.activities.CmAnalyticsActivity;
import com.example.hhdiplom.activities.EditProfileActivity;
import com.example.hhdiplom.activities.FavoritesActivity;
import com.example.hhdiplom.activities.LoginActivity;
import com.example.hhdiplom.activities.SkillsActivity;
import com.example.hhdiplom.adapters.ResponsesAdapter;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.models.ApplicantInterestsResponse;
import com.example.hhdiplom.models.ApplicantInterestsUpdateRequest;
import com.example.hhdiplom.models.CmProfileStatsResponse;
import com.example.hhdiplom.models.ResponseItem;
import com.example.hhdiplom.models.ResponsesResponse;
import com.example.hhdiplom.models.UserProfile;
import com.example.hhdiplom.models.VacancyResponse;
import com.example.hhdiplom.utils.LanguagePrefs;
import com.example.hhdiplom.utils.ThemePrefs;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class ProfileFragment extends Fragment {

    private static final int REQUEST_EDIT_PROFILE = 1001;
    private static final int REQUEST_CHANGE_PASSWORD = 1002;

    private TextView tvUserName;
    private TextView tvUserType;
    private TextView tvEmail;
    private TextView tvPhone;
    private TextView tvBirthDate;
    private TextView tvResume;
    private TextView tvDebugRole;
    private TextView tvCompanyInfo;
    private ImageView ivAvatar;
    private LinearLayout statsContainer;
    private LinearLayout chartContainer;
    private ProgressBar progressBar;
    private Button btnLogout;
    private Button btnEditProfile;
    private Button btnSkills;
    private Button btnInterests;
    private Button btnFavorites;
    private Button btnToggleTheme;
    private Button btnLanguage;
    private Button btnChangePassword;
    private Button btnOpenCmAnalytics;
    private View cardLatestResponses;

    private RecyclerView rvProfileResponses;
    private ResponsesAdapter responsesAdapter;
    private final List<ResponseItem> responseItems = new ArrayList<>();
    private final List<ResponseItem> latestItems = new ArrayList<>();
    private final List<String> selectedInterests = new ArrayList<>();
    private final List<String> availableInterests = new ArrayList<>();

    private ApiService apiService;
    private boolean isContentManager;
    private CmProfileStatsResponse cmStats;
    private int favoriteVacanciesCount;

    private Call<UserProfile> profileCall;
    private Call<ResponsesResponse> responsesCall;
    private Call<CmProfileStatsResponse> cmStatsCall;
    private Call<VacancyResponse> favoritesCountCall;
    private Call<ApplicantInterestsResponse> interestsCall;
    private Call<ApplicantInterestsResponse> updateInterestsCall;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        View view = inflater.inflate(R.layout.fragment_profile, container, false);

        apiService = ApiClient.getApiService();
        initViews(view);
        setupResponsesRecycler();
        updateThemeButtonText();
        updateLanguageButtonText();
        loadUserProfile();

        return view;
    }

    private void initViews(View view) {
        tvUserName = view.findViewById(R.id.tvUserName);
        tvUserType = view.findViewById(R.id.tvUserType);
        tvEmail = view.findViewById(R.id.tvEmail);
        tvPhone = view.findViewById(R.id.tvPhone);
        tvBirthDate = view.findViewById(R.id.tvBirthDate);
        tvResume = view.findViewById(R.id.tvResume);
        tvDebugRole = view.findViewById(R.id.tvDebugRole);
        tvCompanyInfo = view.findViewById(R.id.tvCompanyInfo);
        ivAvatar = view.findViewById(R.id.ivAvatar);

        statsContainer = view.findViewById(R.id.statsContainer);
        chartContainer = view.findViewById(R.id.chartContainer);
        progressBar = view.findViewById(R.id.progressBar);

        btnLogout = view.findViewById(R.id.btnLogout);
        btnEditProfile = view.findViewById(R.id.btnEditProfile);
        btnSkills = view.findViewById(R.id.btnSkills);
        btnInterests = view.findViewById(R.id.btnInterests);
        btnFavorites = view.findViewById(R.id.btnFavorites);
        btnToggleTheme = view.findViewById(R.id.btnToggleTheme);
        btnLanguage = view.findViewById(R.id.btnLanguage);
        btnChangePassword = view.findViewById(R.id.btnChangePassword);
        btnOpenCmAnalytics = view.findViewById(R.id.btnOpenCmAnalytics);
        cardLatestResponses = view.findViewById(R.id.cardLatestResponses);

        rvProfileResponses = view.findViewById(R.id.rvProfileResponses);

        btnLogout.setOnClickListener(v -> logout());
        btnEditProfile.setOnClickListener(v -> {
            Intent intent = new Intent(getContext(), EditProfileActivity.class);
            startActivityForResult(intent, REQUEST_EDIT_PROFILE);
        });
        btnChangePassword.setOnClickListener(v -> {
            Intent intent = new Intent(getContext(), ChangePasswordActivity.class);
            startActivityForResult(intent, REQUEST_CHANGE_PASSWORD);
        });
        btnOpenCmAnalytics.setOnClickListener(v -> startActivity(new Intent(getContext(), CmAnalyticsActivity.class)));
        btnSkills.setOnClickListener(v -> startActivity(new Intent(getContext(), SkillsActivity.class)));
        btnInterests.setOnClickListener(v -> requestInterests(true, true));
        btnFavorites.setOnClickListener(v -> startActivity(new Intent(getContext(), FavoritesActivity.class)));
        btnToggleTheme.setOnClickListener(v -> {
            if (getContext() == null) {
                return;
            }
            ThemePrefs.toggleTheme(getContext());
            if (getActivity() != null) {
                getActivity().recreate();
            }
        });
        btnLanguage.setOnClickListener(v -> showLanguageDialog());
    }

    private void updateThemeButtonText() {
        if (btnToggleTheme == null || getContext() == null) {
            return;
        }
        int mode = ThemePrefs.getSavedTheme(getContext());
        btnToggleTheme.setText(mode == 1 ? getString(R.string.profile_theme_dark) : getString(R.string.profile_theme_light));
    }

    private void updateLanguageButtonText() {
        if (btnLanguage == null || getContext() == null) {
            return;
        }
        String lang = LanguagePrefs.getSavedLanguage(getContext());
        btnLanguage.setText(LanguagePrefs.LANG_EN.equals(lang)
                ? getString(R.string.language_current_en)
                : getString(R.string.language_current_ru));
    }

    private void showLanguageDialog() {
        if (getContext() == null) {
            return;
        }
        final String[] codes = {LanguagePrefs.LANG_RU, LanguagePrefs.LANG_EN};
        final String[] labels = {getString(R.string.language_russian), getString(R.string.language_english)};
        String current = LanguagePrefs.getSavedLanguage(getContext());
        int checked = LanguagePrefs.LANG_EN.equals(current) ? 1 : 0;

        new AlertDialog.Builder(getContext())
                .setTitle(R.string.language_title)
                .setSingleChoiceItems(labels, checked, (dialog, which) -> {
                    LanguagePrefs.setLanguage(requireContext(), codes[which]);
                    Toast.makeText(getContext(), getString(R.string.language_changed), Toast.LENGTH_SHORT).show();
                    dialog.dismiss();
                    if (getActivity() != null) {
                        getActivity().recreate();
                    }
                })
                .setNegativeButton(R.string.cancel, null)
                .show();
    }

    private void requestInterests(boolean openDialogAfterLoad, boolean showErrors) {
        if (!isAdded() || getContext() == null || btnInterests == null) {
            return;
        }

        if (interestsCall != null && !interestsCall.isCanceled()) {
            interestsCall.cancel();
        }

        btnInterests.setEnabled(false);
        interestsCall = apiService.getMyInterests();
        interestsCall.enqueue(new Callback<ApplicantInterestsResponse>() {
            @Override
            public void onResponse(Call<ApplicantInterestsResponse> call, Response<ApplicantInterestsResponse> response) {
                if (!isAdded() || getContext() == null || btnInterests == null) {
                    return;
                }

                btnInterests.setEnabled(true);
                if (response.isSuccessful() && response.body() != null) {
                    applyInterestsResponse(response.body());
                    if (openDialogAfterLoad) {
                        showInterestsDialog();
                    }
                } else if (showErrors) {
                    Toast.makeText(getContext(), getString(R.string.profile_interests_load_failed_code, response.code()), Toast.LENGTH_SHORT).show();
                }
            }

            @Override
            public void onFailure(Call<ApplicantInterestsResponse> call, Throwable t) {
                if (!isAdded() || getContext() == null || btnInterests == null) {
                    return;
                }

                btnInterests.setEnabled(true);
                if (showErrors) {
                    Toast.makeText(getContext(), getString(R.string.error_network_with_message, t.getMessage()), Toast.LENGTH_SHORT).show();
                }
            }
        });
    }

    private void applyInterestsResponse(ApplicantInterestsResponse payload) {
        availableInterests.clear();
        selectedInterests.clear();

        if (payload != null) {
            for (String raw : payload.getAvailableCategories()) {
                String value = raw == null ? "" : raw.trim();
                if (!value.isEmpty() && !availableInterests.contains(value)) {
                    availableInterests.add(value);
                }
            }

            for (String raw : payload.getCategories()) {
                String value = raw == null ? "" : raw.trim();
                if (!value.isEmpty() && !selectedInterests.contains(value)) {
                    selectedInterests.add(value);
                }
            }
        }

        for (String value : selectedInterests) {
            if (!availableInterests.contains(value)) {
                availableInterests.add(value);
            }
        }

        updateInterestsButtonText();
    }

    private void updateInterestsButtonText() {
        if (btnInterests == null) {
            return;
        }

        if (selectedInterests.isEmpty()) {
            btnInterests.setText(getString(R.string.profile_interests));
            return;
        }

        if (selectedInterests.size() <= 2) {
            btnInterests.setText(getString(
                    R.string.profile_interests_selected_short,
                    TextUtils.join(", ", selectedInterests)
            ));
            return;
        }

        btnInterests.setText(getString(R.string.profile_interests_selected_count, selectedInterests.size()));
    }

    private void showInterestsDialog() {
        if (!isAdded() || getContext() == null) {
            return;
        }
        if (availableInterests.isEmpty()) {
            Toast.makeText(getContext(), getString(R.string.profile_interests_empty_options), Toast.LENGTH_SHORT).show();
            return;
        }

        String[] items = availableInterests.toArray(new String[0]);
        boolean[] checked = new boolean[items.length];
        for (int i = 0; i < items.length; i++) {
            checked[i] = selectedInterests.contains(items[i]);
        }

        new AlertDialog.Builder(getContext())
                .setTitle(R.string.profile_interests_title)
                .setMultiChoiceItems(items, checked, (dialog, which, isChecked) -> checked[which] = isChecked)
                .setNegativeButton(R.string.cancel, null)
                .setPositiveButton(R.string.skills_save, (dialog, which) -> {
                    List<String> categories = new ArrayList<>();
                    for (int i = 0; i < items.length; i++) {
                        if (checked[i]) {
                            categories.add(items[i]);
                        }
                    }
                    saveInterests(categories);
                })
                .show();
    }

    private void saveInterests(List<String> categories) {
        if (!isAdded() || getContext() == null) {
            return;
        }

        if (updateInterestsCall != null && !updateInterestsCall.isCanceled()) {
            updateInterestsCall.cancel();
        }

        updateInterestsCall = apiService.saveMyInterests(new ApplicantInterestsUpdateRequest(categories));
        updateInterestsCall.enqueue(new Callback<ApplicantInterestsResponse>() {
            @Override
            public void onResponse(Call<ApplicantInterestsResponse> call, Response<ApplicantInterestsResponse> response) {
                if (!isAdded() || getContext() == null) {
                    return;
                }

                if (response.isSuccessful()) {
                    if (response.body() != null) {
                        applyInterestsResponse(response.body());
                    } else {
                        selectedInterests.clear();
                        selectedInterests.addAll(categories);
                        updateInterestsButtonText();
                    }
                    Toast.makeText(getContext(), getString(R.string.profile_interests_saved), Toast.LENGTH_SHORT).show();
                } else {
                    Toast.makeText(getContext(), getString(R.string.profile_interests_save_failed_code, response.code()), Toast.LENGTH_SHORT).show();
                }
            }

            @Override
            public void onFailure(Call<ApplicantInterestsResponse> call, Throwable t) {
                if (!isAdded() || getContext() == null) {
                    return;
                }
                Toast.makeText(getContext(), getString(R.string.error_network_with_message, t.getMessage()), Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void setupResponsesRecycler() {
        responsesAdapter = new ResponsesAdapter(latestItems, response -> {
            // Preview block in profile.
        });
        rvProfileResponses.setLayoutManager(new LinearLayoutManager(getContext()));
        rvProfileResponses.setAdapter(responsesAdapter);
        rvProfileResponses.setNestedScrollingEnabled(false);
        rvProfileResponses.setOverScrollMode(View.OVER_SCROLL_NEVER);
    }

    private void loadUserProfile() {
        if (!isAdded() || getContext() == null) {
            return;
        }

        progressBar.setVisibility(View.VISIBLE);

        profileCall = apiService.getUserProfile();
        profileCall.enqueue(new Callback<UserProfile>() {
            @Override
            public void onResponse(Call<UserProfile> call, Response<UserProfile> response) {
                if (!isAdded() || getContext() == null) {
                    return;
                }

                progressBar.setVisibility(View.GONE);

                if (response.isSuccessful() && response.body() != null) {
                    UserProfile userProfile = response.body();
                    displayUserProfile(userProfile);
                    ApiClient.saveUserInfo(userProfile);

                    if (isContentManager) {
                        loadCmStats();
                    } else {
                        setupApplicantStats();
                        loadApplicantFavoritesCount();
                        chartContainer.setVisibility(View.GONE);
                    }

                    loadUserResponses();
                } else {
                    handleProfileError(response.code());
                    loadUserResponses();
                }
            }

            @Override
            public void onFailure(Call<UserProfile> call, Throwable t) {
                if (!isAdded() || getContext() == null) {
                    return;
                }

                progressBar.setVisibility(View.GONE);
                Toast.makeText(getContext(), getString(R.string.profile_error_network, t.getMessage()), Toast.LENGTH_SHORT).show();
                showSavedProfileData();
                loadUserResponses();
            }
        });
    }

    private void loadCmStats() {
        cmStatsCall = apiService.getCmProfileStats();
        cmStatsCall.enqueue(new Callback<CmProfileStatsResponse>() {
            @Override
            public void onResponse(Call<CmProfileStatsResponse> call, Response<CmProfileStatsResponse> response) {
                if (!isAdded() || getContext() == null) {
                    return;
                }

                if (response.isSuccessful() && response.body() != null) {
                    cmStats = response.body();
                    setupCmStats();
                } else {
                    addStatItem(getString(R.string.profile_statistics), getString(R.string.profile_stats_unavailable));
                }
            }

            @Override
            public void onFailure(Call<CmProfileStatsResponse> call, Throwable t) {
                if (!isAdded() || getContext() == null) {
                    return;
                }
                addStatItem(getString(R.string.profile_statistics), getString(R.string.profile_stats_unavailable));
            }
        });
    }

    private void loadUserResponses() {
        if (!isAdded() || getContext() == null) {
            return;
        }

        responsesCall = apiService.getResponses();
        responsesCall.enqueue(new Callback<ResponsesResponse>() {
            @Override
            public void onResponse(Call<ResponsesResponse> call, Response<ResponsesResponse> response) {
                if (!isAdded() || getContext() == null) {
                    return;
                }

                responseItems.clear();
                if (response.isSuccessful() && response.body() != null && response.body().getResults() != null) {
                    responseItems.addAll(response.body().getResults());
                }

                if (!isContentManager) {
                    setupApplicantStats();
                }
                updateLatestResponses();
            }

            @Override
            public void onFailure(Call<ResponsesResponse> call, Throwable t) {
                if (!isAdded() || getContext() == null) {
                    return;
                }

                responseItems.clear();
                if (!isContentManager) {
                    setupApplicantStats();
                }
                updateLatestResponses();
            }
        });
    }

    private void loadApplicantFavoritesCount() {
        if (!isAdded() || getContext() == null || isContentManager) {
            return;
        }

        if (favoritesCountCall != null && !favoritesCountCall.isCanceled()) {
            favoritesCountCall.cancel();
        }

        favoritesCountCall = apiService.getVacancies(
                null, null, null, null, null,
                null, null,
                true,
                null,
                1
        );
        favoritesCountCall.enqueue(new Callback<VacancyResponse>() {
            @Override
            public void onResponse(Call<VacancyResponse> call, Response<VacancyResponse> response) {
                if (!isAdded() || getContext() == null || isContentManager) {
                    return;
                }

                if (response.isSuccessful() && response.body() != null) {
                    VacancyResponse body = response.body();
                    int fallbackSize = body.getResults() == null ? 0 : body.getResults().size();
                    favoriteVacanciesCount = Math.max(body.getCount(), fallbackSize);
                } else {
                    favoriteVacanciesCount = 0;
                }
                setupApplicantStats();
            }

            @Override
            public void onFailure(Call<VacancyResponse> call, Throwable t) {
                if (!isAdded() || getContext() == null || isContentManager) {
                    return;
                }
                favoriteVacanciesCount = 0;
                setupApplicantStats();
            }
        });
    }

    private void updateLatestResponses() {
        latestItems.clear();
        int limit = Math.min(5, responseItems.size());
        for (int i = 0; i < limit; i++) {
            latestItems.add(responseItems.get(i));
        }
        responsesAdapter.notifyDataSetChanged();
    }

    private void displayUserProfile(UserProfile profile) {
        if (!isAdded() || getContext() == null) {
            return;
        }

        isContentManager = profile.getEmployeeRole() != null
                && profile.getEmployeeRole().toLowerCase(Locale.getDefault()).contains("content");

        String displayName;
        if (!TextUtils.isEmpty(profile.getFirstName()) && !TextUtils.isEmpty(profile.getLastName())) {
            displayName = profile.getFirstName() + " " + profile.getLastName();
        } else if (!TextUtils.isEmpty(profile.getFirstName())) {
            displayName = profile.getFirstName();
        } else if (!TextUtils.isEmpty(profile.getLastName())) {
            displayName = profile.getLastName();
        } else {
            displayName = !TextUtils.isEmpty(profile.getUsername())
                    ? profile.getUsername()
                    : getString(R.string.profile_user_fallback);
        }

        tvUserName.setText(displayName);
        tvUserType.setText(isContentManager ? getString(R.string.profile_role_content_manager) : getUserTypeText(profile.getUserType()));
        tvDebugRole.setText(com.example.hhdiplom.utils.RoleUtils.getDebugRoleString());
        loadAvatar(profile.getAvatar());

        tvEmail.setText(getString(R.string.profile_email_template, textOrDefault(profile.getEmail())));
        tvPhone.setText(getString(R.string.profile_phone_template, textOrDefault(profile.getPhone())));

        if (isContentManager) {
            tvBirthDate.setVisibility(View.GONE);
            tvResume.setVisibility(View.GONE);
            btnSkills.setVisibility(View.GONE);
            btnInterests.setVisibility(View.GONE);
            btnFavorites.setVisibility(View.GONE);
            btnChangePassword.setVisibility(View.VISIBLE);
            btnOpenCmAnalytics.setVisibility(View.VISIBLE);
            if (cardLatestResponses != null) {
                cardLatestResponses.setVisibility(View.GONE);
            }

            tvCompanyInfo.setText(buildCompanyInfoText(
                    profile.getCompanyName(),
                    profile.getCompanyNumber(),
                    profile.getCompanyIndustry(),
                    profile.getCompanyDescription()
            ));
            tvCompanyInfo.setVisibility(View.VISIBLE);
        } else {
            tvBirthDate.setVisibility(View.VISIBLE);
            tvResume.setVisibility(View.VISIBLE);
            tvBirthDate.setText(getString(R.string.profile_birth_date_template, formatDate(profile.getBirthDate())));
            tvResume.setText(getString(R.string.profile_about_template, textOrDefault(profile.getResume())));

            boolean isApplicant = profile.getUserType() != null
                    && profile.getUserType().toLowerCase(Locale.getDefault()).contains("applicant");
            btnSkills.setVisibility(isApplicant ? View.VISIBLE : View.GONE);
            btnInterests.setVisibility(isApplicant ? View.VISIBLE : View.GONE);
            btnFavorites.setVisibility(isApplicant ? View.VISIBLE : View.GONE);
            btnChangePassword.setVisibility(View.GONE);
            btnOpenCmAnalytics.setVisibility(View.GONE);
            if (cardLatestResponses != null) {
                cardLatestResponses.setVisibility(View.VISIBLE);
            }
            tvCompanyInfo.setVisibility(View.GONE);
            if (isApplicant) {
                requestInterests(false, false);
            } else {
                selectedInterests.clear();
                availableInterests.clear();
                updateInterestsButtonText();
            }
        }
    }

    private void setupApplicantStats() {
        if (!isAdded() || getContext() == null || statsContainer == null) {
            return;
        }

        statsContainer.removeAllViews();

        int totalResponses = responseItems.size();
        int invitations = 0;
        Set<Integer> viewedVacancyIds = new HashSet<>();
        for (ResponseItem item : responseItems) {
            String status = item.getStatusName();
            if (status == null) {
                if (item.getVacancyId() > 0) {
                    viewedVacancyIds.add(item.getVacancyId());
                }
                continue;
            }
            String normalized = status.toLowerCase(Locale.getDefault());
            if (normalized.contains("invite") || normalized.contains("\u043f\u0440\u0438\u0433\u043b\u0430\u0448")) {
                invitations++;
            }
            if (item.getVacancyId() > 0) {
                viewedVacancyIds.add(item.getVacancyId());
            }
        }
        int viewedVacancies = viewedVacancyIds.size();

        addStatItem(getString(R.string.profile_stat_responses_sent), String.valueOf(totalResponses));
        addStatItem(getString(R.string.profile_stat_invitations), String.valueOf(invitations));
        addStatItem(getString(R.string.profile_stat_favorites), String.valueOf(favoriteVacanciesCount));
        addStatItem(getString(R.string.profile_stat_vacancy_views), String.valueOf(viewedVacancies));
    }

    private void setupCmStats() {
        if (!isAdded() || getContext() == null || statsContainer == null) {
            return;
        }

        statsContainer.removeAllViews();

        if (cmStats == null || cmStats.getStats() == null) {
            addStatItem(getString(R.string.profile_statistics), getString(R.string.profile_stats_unavailable));
            return;
        }

        CmProfileStatsResponse.StatsInfo stats = cmStats.getStats();
        addStatItem(getString(R.string.profile_stat_videos), String.valueOf(stats.getVideosCount()));
        addStatItem(getString(R.string.profile_stat_vacancies), String.valueOf(stats.getVacanciesCount()));
        addStatItem(getString(R.string.profile_stat_responses), String.valueOf(stats.getResponsesCount()));
        addStatItem(getString(R.string.profile_stat_video_views), String.valueOf(stats.getVideoViewsCount()));
        addStatItem(getString(R.string.profile_stat_video_likes), String.valueOf(stats.getVideoLikesCount()));
        addStatItem(getString(R.string.profile_stat_vacancy_views), String.valueOf(stats.getVacancyViewsCount()));

        if (cmStats.getChart() != null
                && cmStats.getChart().getLabels() != null
                && cmStats.getChart().getValues() != null
                && !cmStats.getChart().getLabels().isEmpty()
                && !cmStats.getChart().getValues().isEmpty()) {
            renderChart(cmStats.getChart().getLabels(), cmStats.getChart().getValues());
            chartContainer.setVisibility(View.VISIBLE);
        } else {
            chartContainer.setVisibility(View.GONE);
        }

        if (cmStats.getCompany() != null) {
            tvCompanyInfo.setText(buildCompanyInfoText(
                    cmStats.getCompany().getName(),
                    cmStats.getCompany().getNumber(),
                    cmStats.getCompany().getIndustry(),
                    cmStats.getCompany().getDescription()
            ));
        }
    }

    private void addStatItem(String title, String value) {
        if (!isAdded() || getContext() == null || statsContainer == null) {
            return;
        }

        View statView = LayoutInflater.from(getContext()).inflate(R.layout.item_stat, statsContainer, false);
        TextView tvStatTitle = statView.findViewById(R.id.tvStatTitle);
        TextView tvStatValue = statView.findViewById(R.id.tvStatValue);

        tvStatTitle.setText(title);
        tvStatValue.setText(value);

        statsContainer.addView(statView);
    }

    private void renderChart(List<String> labels, List<Integer> values) {
        if (chartContainer == null || getContext() == null) {
            return;
        }

        chartContainer.removeAllViews();

        int max = 1;
        for (Integer value : values) {
            if (value != null && value > max) {
                max = value;
            }
        }

        for (int i = 0; i < labels.size() && i < values.size(); i++) {
            String label = labels.get(i);
            int value = values.get(i) == null ? 0 : values.get(i);

            LinearLayout row = new LinearLayout(getContext());
            row.setOrientation(LinearLayout.VERTICAL);
            row.setPadding(0, 0, 0, 12);

            TextView title = new TextView(getContext());
            title.setText(label + ": " + value);
            title.setTextColor(ContextCompat.getColor(requireContext(), R.color.on_surface));
            title.setTextSize(13f);

            ProgressBar bar = new ProgressBar(getContext(), null, android.R.attr.progressBarStyleHorizontal);
            bar.setMax(max);
            bar.setProgress(value);

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                bar.setProgressTintList(android.content.res.ColorStateList.valueOf(
                        ContextCompat.getColor(requireContext(), R.color.primary)
                ));
            }

            row.addView(title);
            row.addView(bar, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT
            ));

            chartContainer.addView(row);
        }
    }

    private String buildCompanyInfoText(String name, String number, String industry, String description) {
        StringBuilder builder = new StringBuilder();
        builder.append(getString(R.string.profile_company_name_label))
                .append(": ")
                .append(textOrDefault(name))
                .append("\n");
        builder.append(getString(R.string.profile_company_number_label))
                .append(": ")
                .append(textOrDefault(number))
                .append("\n");
        builder.append(getString(R.string.profile_company_industry_label))
                .append(": ")
                .append(textOrDefault(industry))
                .append("\n");
        builder.append(getString(R.string.profile_company_description_label))
                .append(": ")
                .append(textOrDefault(description));
        return builder.toString();
    }

    private void loadAvatar(String avatarPath) {
        if (ivAvatar == null || !isAdded() || getContext() == null) {
            return;
        }

        String avatarUrl = resolveAbsoluteUrl(avatarPath);
        Glide.with(this)
                .load(avatarUrl)
                .placeholder(R.drawable.ic_profile)
                .error(R.drawable.ic_profile)
                .circleCrop()
                .into(ivAvatar);
    }

    private String resolveAbsoluteUrl(String value) {
        if (TextUtils.isEmpty(value)) {
            return null;
        }
        if (value.startsWith("http://") || value.startsWith("https://")) {
            return value;
        }
        String normalized = value.startsWith("/") ? value.substring(1) : value;
        return ApiClient.BASE_URL + normalized;
    }

    private String formatDate(String apiDate) {
        if (apiDate == null || apiDate.trim().isEmpty()) {
            return getString(R.string.profile_not_specified);
        }

        String datePart = apiDate.split("T")[0];
        try {
            SimpleDateFormat iso = new SimpleDateFormat("yyyy-MM-dd", Locale.US);
            Date date = iso.parse(datePart);
            SimpleDateFormat out = new SimpleDateFormat("d MMMM yyyy", Locale.getDefault());
            return out.format(date);
        } catch (Exception e) {
            return datePart.replace("-", ".");
        }
    }

    private String getUserTypeText(String userType) {
        if (userType == null) {
            return getString(R.string.profile_not_specified);
        }
        switch (userType.toLowerCase(Locale.getDefault())) {
            case "applicant":
                return getString(R.string.profile_role_applicant);
            case "company":
                return getString(R.string.profile_role_company);
            case "staff":
                return getString(R.string.profile_role_staff);
            case "adminsite":
                return getString(R.string.profile_role_admin);
            default:
                return userType;
        }
    }

    private void handleProfileError(int errorCode) {
        if (!isAdded() || getContext() == null) {
            return;
        }

        switch (errorCode) {
            case 401:
                Toast.makeText(getContext(), getString(R.string.session_expired_login_again), Toast.LENGTH_LONG).show();
                logout();
                break;
            case 404:
                Toast.makeText(getContext(), getString(R.string.profile_error_not_found), Toast.LENGTH_SHORT).show();
                break;
            default:
                Toast.makeText(getContext(), getString(R.string.profile_error_load_code, errorCode), Toast.LENGTH_SHORT).show();
                break;
        }

        showSavedProfileData();
    }

    private void showSavedProfileData() {
        if (!isAdded() || getContext() == null) {
            return;
        }

        String username = ApiClient.getUsername();
        String email = ApiClient.getUserEmail();
        String userType = ApiClient.getUserType();
        boolean isApplicant = userType != null && userType.toLowerCase(Locale.getDefault()).contains("applicant");

        isContentManager = ApiClient.getEmployeeRole() != null
                && ApiClient.getEmployeeRole().toLowerCase(Locale.getDefault()).contains("content");

        if (!TextUtils.isEmpty(username)) {
            tvUserName.setText(username);
        }
        if (!TextUtils.isEmpty(userType)) {
            tvUserType.setText(getUserTypeText(userType));
        }
        if (!TextUtils.isEmpty(email)) {
            tvEmail.setText(getString(R.string.profile_email_template, email));
        }
        loadAvatar(null);

        btnOpenCmAnalytics.setVisibility(isContentManager ? View.VISIBLE : View.GONE);
        btnSkills.setVisibility(isApplicant ? View.VISIBLE : View.GONE);
        btnInterests.setVisibility(isApplicant ? View.VISIBLE : View.GONE);
        btnFavorites.setVisibility(isApplicant ? View.VISIBLE : View.GONE);

        if (isApplicant) {
            requestInterests(false, false);
            loadApplicantFavoritesCount();
        } else {
            selectedInterests.clear();
            availableInterests.clear();
            updateInterestsButtonText();
        }

        if (!isContentManager) {
            setupApplicantStats();
        }
        updateLatestResponses();
    }

    private void logout() {
        if (!isAdded() || getContext() == null) {
            return;
        }

        new AlertDialog.Builder(getContext())
                .setTitle(R.string.logout_title)
                .setMessage(R.string.logout_message)
                .setPositiveButton(R.string.yes, (dialog, which) -> {
                    ApiClient.clearTokens();
                    Intent intent = new Intent(getContext(), LoginActivity.class);
                    intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
                    startActivity(intent);
                    if (getActivity() != null) {
                        getActivity().finish();
                    }
                })
                .setNegativeButton(R.string.cancel, null)
                .show();
    }

    private String textOrDefault(String value) {
        return TextUtils.isEmpty(value) ? getString(R.string.profile_not_specified) : value;
    }

    @Override
    public void onActivityResult(int requestCode, int resultCode, @Nullable Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_EDIT_PROFILE || requestCode == REQUEST_CHANGE_PASSWORD) {
            if (resultCode == Activity.RESULT_OK) {
                loadUserProfile();
            }
        }
    }

    @Override
    public void onDestroyView() {
        super.onDestroyView();

        if (profileCall != null && !profileCall.isCanceled()) {
            profileCall.cancel();
        }
        if (responsesCall != null && !responsesCall.isCanceled()) {
            responsesCall.cancel();
        }
        if (cmStatsCall != null && !cmStatsCall.isCanceled()) {
            cmStatsCall.cancel();
        }
        if (favoritesCountCall != null && !favoritesCountCall.isCanceled()) {
            favoritesCountCall.cancel();
        }
        if (interestsCall != null && !interestsCall.isCanceled()) {
            interestsCall.cancel();
        }
        if (updateInterestsCall != null && !updateInterestsCall.isCanceled()) {
            updateInterestsCall.cancel();
        }
    }
}
