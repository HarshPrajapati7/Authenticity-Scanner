def calculate_bayesian_probability(
    spectral_score: float, 
    ela_score: float, 
    noise_variance: float, 
    vlm_score: float
) -> float:
    prior_forged = 0.1
    prior_authentic = 0.9

    p_spectral_forged = min(max(spectral_score, 0.01), 0.99)
    p_spectral_auth = 1.0 - p_spectral_forged

    p_ela_forged = min(max(ela_score / 100.0, 0.01), 0.99)
    p_ela_auth = 1.0 - p_ela_forged

    p_noise_forged = 0.8 if noise_variance < 50 else 0.1
    p_noise_auth = 1.0 - p_noise_forged

    p_vlm_forged = min(max(vlm_score / 100.0, 0.01), 0.99)
    p_vlm_auth = 1.0 - p_vlm_forged

    likelihood_forged = p_spectral_forged * p_ela_forged * p_noise_forged * p_vlm_forged
    likelihood_auth = p_spectral_auth * p_ela_auth * p_noise_auth * p_vlm_auth

    unnormalized_forged = likelihood_forged * prior_forged
    unnormalized_auth = likelihood_auth * prior_authentic

    posterior_forged = unnormalized_forged / (unnormalized_forged + unnormalized_auth + 1e-9)

    return float(posterior_forged * 100.0)


def calculate_weighted_fraud_score(scores: dict[str, float]) -> float:
    weights = {
        "metadata": 0.12,
        "visual": 0.22,
        "ai_generated": 0.20,
        "text_font": 0.12,
        "security": 0.12,
        "text_ai": 0.22,
        "embedded_images": 0.10,
        "video_ai": 0.42,
        "audio_ai": 0.42,
    }
    weighted = 0.0
    total_weight = 0.0

    for key, weight in weights.items():
        if key in scores:
            weighted += scores[key] * weight
            total_weight += weight

    if total_weight == 0:
        return 0.0
    score = weighted / total_weight

    # Do not let low-risk metadata/security modules wash out a neutral or
    # unavailable image detector. A neutral synthetic-image signal should be a
    # review result, not a confident "Genuine" verdict.
    if scores.get("ai_generated", 0.0) >= 45.0:
        score = max(score, 40.0)
    if scores.get("embedded_images", 0.0) >= 45.0:
        score = max(score, 40.0)
    if scores.get("metadata", 0.0) >= 85.0:
        score = max(score, 75.0)
    if scores.get("pdf_pages", 0.0) >= 55.0:
        score = max(score, 45.0)

    return max(0.0, min(100.0, score))


def verdict_from_score(score: float) -> str:
    if score >= 75:
        return "Likely Forged"
    if score >= 40:
        return "Suspicious"
    return "Genuine"
