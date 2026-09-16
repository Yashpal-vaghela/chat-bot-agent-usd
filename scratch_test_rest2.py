import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as c:
        payload = {
            'first_name': 'Test Edited3', 
            'last_name': 'Test', 
            'phone': '9999999999', 
            'city': 'Rajkot', 
            'message': 'Test concern updated', 
            'doctor_name': 'Dr. Pankaj Patel', 
            'email': 'test@test.com'
        }
        # Try PUT request
        r = await c.put('https://ultimatesmiledesign.com/api/consult-with-dentist/447/', json=payload, headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
        print("PUT Status:", r.status_code)
        print("PUT Text:", r.text)

asyncio.run(test())
