from twocaptcha import TwoCaptcha
import settings

class YandexCaptchaEnums:
    IM_NOT_ROBOT_BUTTON = '.CheckboxCaptcha-Anchor'
    SOLVED_BUTTON_SELECTOR = '#advanced-captcha-form > div > div > div.AdvancedCaptcha-FormActions > button.CaptchaButton.CaptchaButton_view_action.CaptchaButton_size_l'
    CAPTCHA_IMAGE_SELECTOR = '#advanced-captcha-form > div > div'
    CAPTCHA_ONLY_IMAGE = '.AdvancedCaptcha-ImageWrapper > img:nth-child(1)'


class YandexCaptchaSolver:
    api_key = settings.RUCAPTCHA_API_TOKEN
    solver = TwoCaptcha(api_key, defaultTimeout=120, pollingInterval=5)

    @staticmethod
    def extract_coordinates(response_from_service: dict) -> list:
        """
        Извлекает массив координат из пришедшего ответа из сервиса rucaptcha
        Пример: {'captchaId': '79577524552', 'code': 'coordinates:x=48,y=125;x=220,y=80;x=147,y=129;x=41,y=65'}
        """

        return [{'x': int(p.split('=')[1].strip()), 'y': int(q.split('=')[1].strip())}
                for s in response_from_service['code'].replace('coordinates:', '').split(';')
                for p, q in [s.split(',')]]

    @staticmethod
    async def solve(image_path: str) -> list:
        result = YandexCaptchaSolver.solver.coordinates(file=image_path)
        return YandexCaptchaSolver.extract_coordinates(result)


