import time
from datetime import datetime
from typing import Any, Dict, Optional
import httpx
from app.providers.base import BaseProvider, ProviderResult

TOKEN_URL = "https://www.cathaycargo.com/content/cargo/en-us/home.APIToken.JSON"
TRACKING_URL = "https://api.cathaypacific.com/cargo-shipments/v1/tracking"

TOKEN_HEADERS = {
    "accept": "*/*",
    "sec-fetch-site": "same-origin",
    # "Cookie": (
    #     "_abck=FE100CE46642C683A27712BDEE1EEF9C~-1~YAAQt/Q3F5Uax+igAQAAQ8kV8RAjItfEBOYkKPHZQQYUHCTWbT8DjTRfjQ7+HipaNDz4zMIVenKV9iEnVoAMPR/Tb8+hahbGe6eGsyAHvMWNVQjW08YdweW+FaRhRDGy0fLsAlmC+ukYqBKf/7M1OeI8SMii5bj16+Uw2QCXbg5o5GsTzaFg7YEB5bvm9aN9nh2nLkrXa4Z1xV2SaC04iGm17avjAvht3Pg5bI/iDPr4ZoZgfvXdVSE2/MYCRxx8ltZnTENl9QFWXCWxAmRrT11+bNk01xB6/LssKPUaZvKnjMrQenM6y0LngwXr+kg0uDu9uUTxDIZaY1awdcUcsnO7D+hh76WuV/d0bz++FJMV3RamgGsNrPEDoKvG2Rt74nP9cc/UanyEZKYwyxMmxA4f/WZ1G+FtaXKnW5sMMZ9odnNIi9nY1drUbmAFoNDFCJGYhfHZEXtB5Y6hSCwAOwSQ/24Xvt0jP+Hp3qUnBoQdqvB8jW52SXsJLmz3KovBBXj3CMlwXjsZm4GAvIS+Ry9fVMyK2xjn0MPXZ29g3pjIkvzxA3Wb1UpHRW2H/akfJQuOzYr4i35ZQsOc7SJBLLk/QKDqiD+pG3PFcmek0b8vUS2DGI9OpJ9rwWIBr/ZQ9K49nKvFMBPX59Lz7u9Rz7WzhEku9ahmx851QUOG2rjBUUkC97eXr3Llmk6/4FtC9+trA8aceNVL6Vwy1XylxW0beZN4V+yG~-1~-1~-1~AAQAAAAG%2f%2f%2f%2f%2f5ktq0XnUEiDlMgraJq5Ex2bRY+MW9230sEUIiwjnvZSywvktpCj6UmdwcvfIQF98PosQ5ZFGdL242OUtFfjkJbQ3gcjAn4GD%2fSymCVcOTMzO7TKKwXNQYKLUG9Fmn6PWpLS5ic%3d~-1; "
    #     "ak_bmsc=DECCA916B715B2585B46069F1A5C2A9F~000000000000000000000000000000~YAAQt/Q3F6iLx+igAQAAS84W8QGFLvLtjPk/uvTHQzeIzJvSo0iXaP2HId750W0vXBGtFaX7R2f2/2E7rSHK6cGXrpeEdKgpzeQyrcRXCzzR+TdRHyTcrYjuQypASGYy0E1dBfpDR2xkc/grTZePt2hrO78tjpah/l4tZyt+1kCg8hzcuuEHFnfImuIX95p/L+B0pQQCBjHaHmOP/xoF0N5ukRQt9Tju/Nw7MKkT+SfoziRFWTTTx0zvnLLBwJlBdnObc/jKpagyadj5s7vVPz9Jp4ggbPEFJRqId86p1n4jLcIqebIPkLlZr89aIq9m/dKbREwHd+CjE3+j8O9HrDQKZXcNsD9A7nYmgJH55PoEqn78/nC0Y6DpL7wfD5cDXVhss4X9dbhbUmxdiQmzhPXm7ov63GJdeZAZL/qvCkkiDFk8pfqFqM2WBG9xXb4zcYEe4q8pjB5HVC8IBf2ROxNMjx5623KJ0Mtx6Izw6DnDlIvKjx6ChAiMQFxVfvRP9e28rdVUgJwnh6ISYLtWQRbnZMHyaItOweXZewPb; "
    #     "bm_sv=9F354B959A78B67B65CD3E286E14EB8C~YAAQt/Q3Fyawx+igAQAAoyYX8QEbq9bkt8cnpHQ6Ub2pPhUj4AHZbr4vB1ycbKBhCy0/z/EPEd6lq0ca9uvLxZFk/I0nubPnGdubrkZxf3BaL04CXB/12hCs/1QIR2r6twusmSqMvRSgW6276p6zBUouDDysqlBYFqD7lJnj2PdmvpB8vhhEiRs6Hlr9LZO/f9d3H+9p60PIxqpcPoZgXibzuNThkYUQ60hqG6K+OpJqKQe/uXJTAt2UAubZTHQefCb4/p49~1; "
    #     "bm_sz=25ACCBA637AC287689AC364F5C7CC6C8~YAAQt/Q3F5gax+igAQAAQ8kV8QGlY/nY5A9nXRUBdeS1HbnstRkYaldMEsTyRhOhOl/HKYuw3u4DMMJ0xgTJJ8oCGvURgPD2gvzTV7hyq2VdSUfCMDKnH59oNQN7ewOMrZClqnbid2UaH18JG05Sv3UGzLjY8FWCKuQ82dSDDhblpF0myEa3iTlo1fJl8uWI7SKWqponQ0WMnXPeexHqZpb2poLJEyvbStoQaE61izSIp0WWATNQyfMF6cL4rgAFSKqDhwsmA73bap03SxJVt9dfA8+crlBZnRYgwlFiF2vcDoHK1nKN2VM/M5tBX+LvjfSdDVGyAOJcNkX5JnjcoYu89dAEwU3vLN3mj3RsXZmO1327zqNczjYLhA==~3425075~4601665"
    # ),
}

AKAMAI_BM_TELEMETRY = (
    "a=FE100CE46642C683A27712BDEE1EEF9C&&&"
    "e=46FC6BB5B4013AEFDA643C57407EB3D1~YAAQJRzFFwPyIO+gAQAA7lET8QFh1IrNOZ6TWDq2ce9qqLSpFTzarLv2Nv8el1cctCg8QsdBw81HA82GR9X5KQ0MdufMUw34sctN7km3Bw41ypzpoKPGx/ej7kl0Q4f6TpNOT9kZX/iDWA/SzaIcZBkqcZXoVnNcVx/xg0Xzt27/rrHWfnQMoG+mJQU8C0JTYLlwEipfTM0m5X7so7YNSzDn5kzEhutBOskfxvPoxqFJp+ZsrFyCkDF5b9Tn+BtF6KVwqgmjUO3D+lmzf272MXvowdR+fHaupUIvTnASrgw9KhnmCEUrE8pLOrxM+0XzTVwsQDJDPp70aUv/Ks8aLjSjT9o3zlI+3OSd028UP6+QJkLGeMk4VX16NfvQMYAeaG5VIIXGFNHsQABJNQ0PuLD54moTgr2deNQBpmb80lbdTLXsVm+GZDjsT4Mm70wvUI2WpqGj1foHTgnNJ9j68gk=~3359030~4338742&&&"
    "sensor_data=MzsxOzI7MDszMzU5MDMwO2d1STF0SkVFVEZyVU1xU0tVVFBXNHg3blZlKzJjTWhkZTNwY0dOdXl4WWM9OzEzLDEsMCwxLDUsNjc4OTsiMSh4YS4yJWBuWyJqSDQiQUopIlgiUFBbcy9ac159PG4teDFdTlRUID4oZFUxLldIIjkiLmdFIiEiIn1MfiIjMFkiM240VlIiTjd0XiJvIjdhIjsicnIvNyJ6VChlJXAkIjldTCJmbTFxXSIoenQiaSsianVqIjFfZyxyOjErQCJ0STVYOV5ud0tFIm8iUTYibyJDIHpkIjYiU2E1NC1iR01OflciQSIrTV5PRT5TIl8zdiI4JiJwelR6dVlVLiAiKSJKX10gIjFxa2hWZmoiUkJGIjEiJkVmRHl6ZE0qNGlOZzAjJFJ9ZktdVVdofm9+cFp5TVNKeDQtY1FCRjcwZ1JxNjtEdEQ8NzQmSktqdCF1WiRbYnQ+bmMiLiJeXVUiWkE1IiZzNj8sInMsLC8pciI0bUxVUy5hRz5DNUg7NSQpVzYrR0F2bEAhZ1A/KmxHKUxTZ08mNThlemMhcCgiICRCIitBdiI2ITk4W2BmaiQifkU2IjdrNiJoeSEiaSIiVj1pIi50biIuS2B7VyRDIlZpIixPYSJ9dG0vInh5InUrYCJkZyJwJHlLXyJScigiMCIpIjQiKiw7NyJpUXcieyx2Ik4iIk4iXTNKImsiNnAoNDA0VyJ9ImMlSGUiPyJbXk8ibSJtWzQiOiopRCBMcytZWlE7YyJJV208RnsoVFp1a18sIkNMZyJTdW4iQiIiXSJXWisiI3ExPG02UHctIlBPQ2xwInxCVHBDOkUiIiopcCJwRnoiQVhkP2c4SyMlIklFICIqInJQTHNpOz5sIjYiWlY+KSgqSCJqK1oiTFEtImMiR2crLFEiTUV7IjcjaCJpIltCTVZ9N3hNL1UiRnp3ImVGXiJqIld5Ii4maGQoIj8iKDZFUiJNIiE9c110U1RwY1JbdlAvUiJoIlJOS34iKiI6T3JySW1wby5ZbzZkQltPfEtHdmIpIVJJR0U6KDkgM1Y0ZC15SWwiRShsInchOyJZInEwZ3JRalIiTUMjby5ZWyJKIiJzInx7biJYO1sjcSIsTTR+IktSRSJHOHkidjMuLEciVykrayJ0ImFYeEU2e1M1QSFuaT9TZUN8fW5LICxBQmQyZyhKQDkucFU7dSotUjk9KDo4ZmtEIThNbEl6JUEqaEcxI3R4WTVGcDRaXmVydD41SXEvR1ZpcSJhSSIjKyJjIiJGIkI6SCJSJlBRYC5ER0teb0NEb3oiJHwifTJGbTtdVF1OXncoInYiNSJCTz4+InRvIlkiMmdweCJZbDFvSk5Pa0wjbSJnc09IIkcrdWNeaCJIdDxPfjNHNCZGV085IiNRTyJULXEscSJQZl9MZHA2ZEJvQ2Z+K2RTPnA7dG8jckdVeyxPR1A6LSJoW14iSyI8elgiTyJ0Si0iJj0iO05OIGVeamRxOyJKa0sqL1EiKFMiO3w8InU2OSJAIllVaXhEXSJNInlTTkwiTn5CImlfe3REIi86WDE9MDMiVF8rRCI7Ij85XWdtdj5IWFopNi4lN3RgQCxLMVp1IGhsbjZXeHJeOC5Ie2FaXjpFPz4sd1NAe3pTNndXdTZwWl9sNUMudl88ay04OC91VWI4MXpzU2BiWE5wUHw6PlQ4Ul4uTjlkTXpdVTE8WEowcixvQS4kIyJsIjIjY3ciMHk3RmY/cyIwWlIiIyIiKSQxInxdSyJ6MUw7L3JPfDQ6K155IldQNCthd0B8OWFSSlgpaCI7eD0iZCJOMSw9bG5hfkMoWEwqKmhkQCQ6aWBULlQ+fjgtNChLQFE9JU1wenI9aEsqI2hiSE4mdkZgWF0pYl5JUElvZSV5M3x6RSF3ekV8Z0FNMEMyKGddKUxpYjZlXVFoby81U15zXV40ZXshTnhqWVpPW0ZgQTJVQkZYOmhdYmskTlR+fkI7PW1PZXtOJm9Zamh5Z31dZDN4ITkkXWVicH5EZjw+WlplR348VTVva1JvZ3hxKygjWjdhcl4uTVJ0MFJuNkh0cihsXWYvb01QRWFrMSA8MjZ0ZyFCKnAmN15rRWc6VyQuMihoMGBIKy0vTVN0Izw0TSR6LWJHQldnOU4vWzNFKDVCRyldamBGZXEoPFBrOD1DOClTeWZocitfMms9fDpvKkw0PGAzIXEvPE9yNUh1Jjc2JT93enAySDZVS21SdGBvNzA6Zy84LURJdz5oeUxbdXJ0QXl6fTdeQ3JlKCpROUd5fiZOLTo8SmMvWSFQJDpaUF43bGt3TW1UfXRNSHFlL1tgZE4mKntMZj1sQmU7VCAmNXhVU2k+W0YqKWNsOy1NKDRLL156dEZmSl5UKVcrQU1aRCA7UStfPiwoaF5FPHBLW3NMQ09bN1RCZ0wxay1kbSh3UXR3Wzk2c3VlZ1ZTe152NCF3KjdlOSFOT3hoJW0mPHlzNFUzam9NXWFeVEQmZipKPzU9YUF4VDc5aE4ucXk/RC5dbVo3PC1LOEAwRX1WMlZFNWYsXjowdWE+OGxWdT9BKWMxeVBiWWhuKHRzY08hTUhSaDYlZVI9Pyx8U0VWLC85bSYlYiAjOCtMSWNRN2k9Rj9xOSRxa1tWUEEsI0EhdCtNK3dzJi9ITHt4LHx9Ti00N2sxMXN0cG9oa1pJIEVddU8gIHV6L1ZvMzxLQEt8YGl1WCwoc3xwdXx8cnFCdiVGIVphWSUsZ25EOWNZZk4qPFU2bXVdbG8mKi8keFYyVHVbOEFQaH1AZjNMfnJ9Xk5dKG5OSj1aYiRwLyMqclNtLiBjcSFMXTFdM0BoeSpvailBMHJ5fTZCYWEtezlsYy1KPSY+Om4pcDBzMFhvKXtkMVRGQERLZWo3U2Zzd11hKEpGN1FnTFo/Zk1qS1N3dmU2aVY6XV0wSHEjR0xaYE14TEdDZHFGe2I0K04tPWFQVitdWUtyfj9SLEUkK0dCL2EySkBoMFc7I1c1bk5pPzVKcURETmcoS2NRZTRFcGJ1T30kIGBuazklalYueUBZZnxUQjo6UHxLdld3VWc4Lz96V3B8TmxWKiFeajwyTHs2RzJdeShNa0F0T3RPe0pJWD0vQk15VkEjIGxpPTBlQlByWDFIVXxINF5Bc012VmdwVkVdI1EuI2BnWk4+NXJQVXdiWXktTyFnQS1rTGpabnloVSQ3d05UP0k/Oix4YkRiKHJ2MEZ8TUVxbk05WUZPJmVlJEs0fHlmcWd1dHZYMVN4enk6YjRwYUcvdXlHOE5qYl4uWkgoMiU3PUY9UDJ8TnZ5ZjtSTHV6WFRLRXhWKFRPYS1SRDEyNkxPbWp0Y2IoYGpkNmJNIyVufWFkRC9aLTMydEo1M0FAWGEkLTwuI1U2OUltSzwjMX0hbXtVVyFgaGhKISByOjZVdDQ5R0w9KVt3fEwyeXJ4d3slKXVtP3Z9QyFbXVp9M1ZmLjtZX11HeDdEMGdvV1hdcHAhb3ZPNE9qP340NlZ4QE4jOVVQZlc7WnVWJTsjTEdZZnB1elEuWXFdTGVmJTxoOmwrV0lsUjtdfm5dXlR1cz4/ZF9oTC9gdHZWbiZaeEtrOmUrRVZISmYmemxwbT1KciFBPUkzM0p0elYmK2skZTp8Q3wsNTMuYiAkd3klSGomPGVwMCZwOWZja348bjYuTj9dSFZ4ICBJbmxaKDFjcUBjNEFST0R8XVZdbTxrSil0Wn5fe0g8SyRja18hfVp6XXBQW2x2cEwgMy9kM29EKHFRNXxCem4kWjI3O1tvWSBObUZmOzdAeEtqbUNmWjEsaGcxeE9+NUR3Y2lxQlQ3a0JxVWtAM1U0dyw0dEI0bG5NUjx+VjVDTz95QENwNmlEKWZCZ0JJZUkxR1Esb2RFSSo8eHJMMTtnVkFQXzZdUChlQiZPKUFSRTJacVErIHF0dn1gXjl4Ol5MPVh0XiNzQj5sbS94KEdDPE9uYkxOME03Pis3c2UqPUU6XnFeNjFtWjg6XlRsKTEhUSBnOk5NYVVsT2pHRWM3N31Vel0yLX17Z1Quey9yZnFHYF1ARkZkbC56MGlsM2hvbkFjUjkycSRrb1BGYTYuRXxNQzNCSWRjNSxQMjhhNTtRd0k5eSp8KnQkaFoqXWN0SC1+eywoYmIuMks7SyVlZXBPL3xlZ2N3c29mWTR7fTpiR05VbHw/TCsuUj5JK3olOHVRQD5LU2hMb1loN3YsUitwcHc1RSk9bH48TEQ2dDtENHN1ZXl2O0FaU0cocy1ELik4PlZzUGJBVTEwPy11QFVAdzU0SEpheisoLnpwLlAvNUlZazt8OXI2WmYjaWk1VkMrOz1SXzFHaFl0Vz95MjQgOlp8SSlOKVo3TVVJV2lELDBAPmVvR2IrfkQyL014I283TTRWO2FKeVFnLSAyYSh6fig7YCZdZDdCa15YJFhaX3k4ekY5algjZi1UQ14saVlidjNdelh6SFF9aXpFKjMxWiReQTFrVDByOFdmblYlLDFOa0FnQGhKY3ghNGs9W14tUD8jIVBGI288aHMtcU5jTy5CKkI0Uz5VciFGdVdte1Z6eVBQOzhwYzttbjUkZnF+SHJUI28wdDV3fDgmZHYyeUo0eSlzZFFFJVhwNXdscipgLXRVM3NaIFlkfnFYdDQrX1I+QjUzLiNpQlt8dW4gMm1HNF5ZMy5SM1ZrWFF9MyNhW0dlTl1FVT0hQFldXnU+b0A8enxdSXxsekE9PVQpd1RbVWJnIHJ9X0huQ0E4aSxoQ0Ate3FfNX1HbXhxQHFSR0dPa2sgIyt6eEFnbnk4Zk0vPil9aGtNNV46QDx+P0czRzZfaX19ODowWTI6PGpHL3h2aGxubV9CeUxSXTt4c15+d0VKcyE9NSlpUF1lOmtiRVVRaCJTIm9XKiJ4IjQ1O04ifCJDZDcqInMiWCJDfHUiZ211IkoiOyJDYGEiNTQqIiUiYUMiYHNjIiY3WEMiRTpRSyJKfn0kIkYvcVlKU2dYNXIiTWIvJiJUImwpZE1STllxIiQlQiJ7LUtsIk0yUSI9cTAiViIxSzMiOl5AIiowRFl8In55MGRII1siO1hwOyI3Ii5vQ1giY1h4STUiIzpJIlNpMTdJLS5BIm9VfSI4IndTY3hBMElCRWdkSDVwYX5LdjBhSU9RKEUmWF1MVlZ9Ymw1TXc4LTI5Sn5iImEiKFYpIkhQck5KSXp8fC9YKjMiayReOGMsK2M7a35sPSVtLV8vcSRQLjE7LTM+dUJ0KTZ4MmZdazlVZTx4Q3JMWzVUQGwqYD5hbE00PVg3UkJKNzIqZzpXcyxDfSxjJkxzYUszICFZKS4zQjdJZkByZkRGNyE+QyFYey1EOE9bLV1AIk40aCJlZi4iMSIiNiJSYl9gIkk9dmd5OiwpJE13IjBtRygidXlJIkdEbCAidSJ+VENNOzU6RzBFcVp7Vz5oPSJ9Ij0hajMiVCIidX1RIkJKSCJ8RGNPfUBHZmcicX49Lyk3Z0hRfCJ5QUheYkBKdVgifSgudTU4XzZAbiJZIjN3elsiQSJAIzQ5IkB1InI0T1AifiIicSJhWXUiOkdkV1dSTCkuIilqO3pSKF5NKjsiP1dQbVkid19uIngiU2hnX3IiKiBlImsjKiJrTUdYbk4id0VbXiJNIjBGKlhVRVlVaGpuaWUidyIvK299IkAieDZlazoxQyJtIiwjYG8iIXIyNEIjM2kiY2kidCUqQyJ7VyFHInUiY1FzM3UiWyJpIUhKImhyWDRhZiJJQCJabjlePl0sO0B5LlciTF5nInQiMV4rJCJ6IkI6JXRfdnFFbVEyU3UibyI9LlNGIlMiTGpIM04iOiJsUSx7IkYiMlcwIkgiN10vJiJeIiFwLjZZcExfK0NNTkAiMUw3IlVLYFkgInFHZC95IXI+TSJSbDpSPVMgN09MR31aZWU/UEdzYCwmYUpfLzZIeVRYVXwyZSxnMWJzRUhMKFdzeEdrWDEkZVc8IyIkIndiPiJwIlo5W0EiNiJRZiAiZ3IkRCZgIn5ycVQiOmF2OCFdVm8vIn1UIjh1NGluK3RYayRYNCltbFdAMSMiKThWIkxscElzTzNeQyUidH5ELiJaInEmO2w+Sjd+al9iU3phIkwidlM4IjAiQiVYInxxWSIhIUVQQCJ7dG1zVSROaSJCekoiZSIvIlFOcSJffXUiaWlHOUouayJVbX5YInoiPjlVeSIhNF8iRzZoIjpZVSJzQ3kiSz5TIkpqbWAiMiJhbD1jS2Nmb35fR3d9X3dYM31UQUJTbEtYSkB6NnxkNDxAflFWOSkyNSs0cm8+d2VlcWNsVWJ8YCY3PEUrLkdXO3A6ZFUmaS1vXVNqTy9eankiNiJ5UGl7Imk7ImBrYGh+IkkiUEsieSJpcyJVXSIzZVk4Ij0iPXs2JToiVCItK0ZpIigieC8oJEpXXS84dW4qQlVka11EVGRtTyUgMEZwK0Y0d3hwVzpSVkJxey53cllTck0jK3VLQEA5L0IqSTcuVDxWOCJnLkMiVVZsInIvUEsqWlMiOHk4Im4iKEg2LzNMPi1ARVN8NCJpXiUiIEl2dngvMV9NMFo3Xkg/al4ifEBEInQiZzpzO3xwRGpeMmAiLCJMfmBEb18uIk4iIFItT1VGIWZSbGt1VyNIQSEiOSIrZjZ4Ij0iIiU+LSJKICI0NDRRayVaISJ0I0YiKSI7OkFpOVY8PWdkTTllZ3ZTPiEyNF9odldDKmI0QjZfQH0rV2ItcEU4LCZGWDZ9N0k4bzA3Und7Sz9jRkJwY3ZgRG1KR21sVHBPeyElUi4/IGxebyNVflguKEBfP2x5Si48XXhgMSh2ImsiQ1kxeSJfQDlTZktuXSR1TSJgK0pmIn0xQTVfIkBFTCJlWjlWN0VJaX08dDgoIyFXNXpGInd0eDQieSIiPCI+PTciUCIkVlBubDQzcSVkTEo9fVtuRT5Rdy8rZSJlbncqIl8iN18rOTRnfngiOCwkIk5EJCJHTFRuNkdJbTwiR111IjoqS1gzIkJvaiIhIiFARXJyPTBXKlVWQ0RsfUMvZERgRW9XY29tRnAwPWtQM3YsMShabSIldUciO0JeIl4iLj9DSXZieSNpRjwvPipMR0k1RClRbnRqPlJJdXZVajxQXWhzVENRdVQyKSA8OEtaY1piOC01WEUlM0Jwc0pjQFR1KDZ0ayxAM2cjfiw+S1Z3ImsiMkFvInNwezdNLWlzNWlwIShjfFZALEwqT15HIFlyaFNeaiVpWyFNXyxkVH03WnAmQ3VPa2ciISItNm8iZyI8Til7eCI+a2giZkZ+TzwiRCIrMiJLInNTUyUieSJKIllbTiJRT0IiSCJSImEib2omTCJZIiJFQVYiLjwlIjgiUSI9LUoiS285InlhNSI3Lz4iOTVwTVZOdy9afiIlIlkzOUIiYFtpcDhQKHQ0JlNxIjZ9VDJJKFBPIm4iV0R7QyJsIis8Syk8KCNVaEljUDZSIi82JiJCIiIkIn5vOiJkKXs7eyJhcnUiQSwkb21USSNYWipXIlFsMU8iRVEiOjgiS2ZNOCJQQ2ZoIkJZIj5MJmwiST4jIjF9NyIqeVM7Iis/USJrLCIoIktXY1giYCJLWCAyNiRdOUVyZEk8IisiKDFoZUklPiI6IlZ6Znp4QmFLa0FJVmduWkYiOiJdTTIiXSJqJk4iIj0hRHsiKiEmZ2ktY15hLFBDJCJkIi8tcyJNcXJyZTc7XnVzNDxEUHY0I1YlVCF5LTFuaG5rbEJGOWFWImEiVXByKCJQIipbb2NnOyEqIi4iOmx+d3kjLCI4IjNDTTNdYSJ7IjY1ZSJdIlsoeSI5IjlLREoiWyJhREh6ZHgpflFNTXkoWGBBSnJtdWRMYmtSMCwtQj5eUGtbVD50P0tAMDY7Y3RBYzZQeCEpfVp6PX1pbWt0MlBQaW5lTzlMcXBQYnc8TjxRK0RxJjQxdDxoUTVEQ15qNDdoT2BSOWooIWk3SW4wfjdtO2J+NyQqQ3JbUGJpJEVtJElLYlBAZz4rJVJfPV0zYFN7UmYrfXlOd353LX1eZzpYIDNALixmMjQtTmpWJWE1I1chUGVrd0h3e20oN18rUn1NZSp0IE8wLSZSeF8veVZCcWN0QUZWJGR4bi5JdT94RGchV1FUNGlwJEN3UTIqbWI0K1dwIy91RFNYfUQoOClMK0djcXJeQ09rO2FLKzBnak80aEA8UUkkOjtnI3FHfVFDVSopPXt0KjhwSTJ+d2BeQj5yV2x+Z1lpdEd4Ui8hSzlgKDtVOzJJY0J5fl1sYFtQM3BUdDktdDQ4clAzcFo0elkvR2tgSGV4Z0JFOEVFQzQ1clF3Ny59UGRIcmg9QnZxNnw/Z1Vacz0uaGZWa2Z8cH5fVXVEKzJOeGozL3NpR0khZ3pOQkx+SD8mISgvNUhHVjk5X30kOFt4X0A9LS9we2Q9XzM1MnJBPiA2NE1Rcnchb2U4eHUpYHNtQU82Szg+LHwycnd0US4qdj8/VWs1NUY7OGNLZmVIaVg/VT9TQUoyPGo8V2A8c2hxKDNrdDhFVFFYL3gqQG5NSzdGTyJOIiUgUCJ8ImgiVCJXI19qIkciImwieSwiWCogUXRrViJdUFMiayImMXwzIl1pMFR5I3BwI1lOcTB0PkFbeWt6Lz4iMnJiIm0iR08iaGVxIlAmW2wiaCJ2InlpZiJ8fkgiRyI6LH04aGJHaGdMYEJzP2k+SGxSTzEiOSJhfEMiTVJ1ayJgTX00IllxITkvbSI6fFdrMXw1LiN4cXohIiQiW3A0SDU0YCJeInIxaTN6TiJmIkszNjEiPCIyP140eVFyaHEyOHNEe3VMUHJXdTtGOmc7PVVhZTh6ZFUmLTVMIEt4OWQ9RH1DMFMuXUFqNGZbIiEiTmZhImIiInFCbiJuJF4i&&&"
    "j=AAQAAAAG/////5ktq0XnUEiDlMgraJq5Ex2bRY+MW9230sEUIiwjnvZSywvktpCj6UmdwcvfIQF98PosQ5ZFGdL242OUtFfjkJbQ3gcjAn4GD/SymCVcOTMzO7TKKwXNQYKLUG9Fmn6PWpLS5ic="
)

TRACKING_BASE_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9,hi;q=0.8",
    "akamai-bm-telemetry": AKAMAI_BM_TELEMETRY,
    "content-type": "application/json; charset=UTF-8",
    "origin": "https://www.cathaycargo.com",
    "priority": "u=1, i",
    "referer": "https://www.cathaycargo.com/",
    "sec-ch-ua": '"Chromium";v="154", "Google Chrome";v="154", "Not A(Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
}

_token_cache = {
    "access_token": None,
    "expires_at": 0.0,
}


class CathayCargoProvider(BaseProvider):
    name = "cathay_cargo"
    mode = "AIR"

    async def _get_access_token(self, force_refresh: bool = False) -> str:
        now = time.time()
        if (
            not force_refresh
            and _token_cache["access_token"]
            and now < _token_cache["expires_at"] - 60
        ):
            return _token_cache["access_token"]

        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            resp = await client.get(TOKEN_URL, headers=TOKEN_HEADERS)
            resp.raise_for_status()
            data = resp.json()
            token = data.get("access_token")
            expires_in = data.get("expires_in", 3599)
            if not token:
                raise ValueError(f"No access token in response: {resp.text}")
            _token_cache["access_token"] = token
            _token_cache["expires_at"] = now + float(expires_in)
            return token

    async def track(
        self,
        prefix: str,
        serial: str,
        tracking_number: str,
        language: str = "en-us",
        force_refresh: bool = False,
    ) -> ProviderResult:
        start_time = time.time()
        try:
            token = await self._get_access_token(force_refresh=force_refresh)
            headers = dict(TRACKING_BASE_HEADERS)
            headers["authorization"] = f"Bearer {token}"

            payload = {
                "airLineCodeNbr": prefix,
                "awb": serial,
                "languageId": language,
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(TRACKING_URL, headers=headers, json=payload)
                latency = round((time.time() - start_time) * 1000, 2)

                if resp.status_code != 200:
                    return ProviderResult(
                        success=False,
                        provider_name=self.name,
                        status_code=resp.status_code,
                        error=f"Cathay API returned status {resp.status_code}: {resp.text[:300]}",
                        latency_ms=latency,
                    )

                data = resp.json()

                routing = data.get("routing", [])
                origin = routing[0].get("origin") if routing else None
                destination = routing[-1].get("destination") if routing else None

                pieces = int(data.get("pieces")) if data.get("pieces") and str(data.get("pieces")).isdigit() else None
                weight = data.get("weight")
                volume = float(data.get("volume")) if data.get("volume") else None

                latest_status_block = data.get("latestStatus", {})
                status_str = latest_status_block.get("status", "Delivered" if "Delivered" in str(data) else "In Transit")

                events = []
                for item in data.get("shipHistory", []):
                    events.append({
                        "station": item.get("station"),
                        "status_code": item.get("status"),
                        "status_message": item.get("statusMsgDisplay") or item.get("statusMsg"),
                        "event_time": item.get("dateTime"),
                        "flight_info": item.get("flightInfo"),
                        "pieces": item.get("pieces"),
                        "weight": item.get("weight"),
                        "raw_status": item.get("status"),
                    })

                latest_item = (
                    latest_status_block.get("items", [{}])[0]
                    if latest_status_block.get("items")
                    else (events[-1] if events else None)
                )

                return ProviderResult(
                    success=True,
                    provider_name=self.name,
                    status_code=200,
                    status=status_str,
                    origin=origin,
                    destination=destination,
                    pieces=pieces,
                    weight=weight,
                    volume=volume,
                    events=events,
                    latest_event=latest_item,
                    raw_data=data,
                    latency_ms=latency,
                )

        except Exception as exc:
            latency = round((time.time() - start_time) * 1000, 2)
            return ProviderResult(
                success=False,
                provider_name=self.name,
                status_code=500,
                error=str(exc),
                latency_ms=latency,
            )
